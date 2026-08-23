"""
饭饭之交 闭环测试脚本
覆盖：认证、分类、标签、菜品、图片、订单、状态流转、推送、系统配置、用户管理、游客
用法：python e2e_test.py  （默认 http://localhost:8000，可用环境变量 E2E_BASE 指定其他地址）
"""
import asyncio
import os
import sys
import httpx
import io
import uuid
from pathlib import Path
from PIL import Image
from datetime import date, timedelta

BASE = os.environ.get("E2E_BASE", "http://localhost:8000")
ADMIN_PASSWORD = os.environ.get("E2E_ADMIN_PASSWORD")
TEST_USERNAME = f"e2e_{uuid.uuid4().hex[:10]}"
UPLOAD_DIR = os.environ.get("E2E_UPLOAD_DIR")
PASS = 0
FAIL = 0
RESULTS = []


def make_png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(output, format="PNG")
    return output.getvalue()


def record(name: str, ok: bool, detail: str = ""):
    global PASS, FAIL
    if ok:
        PASS += 1
        RESULTS.append(f"  ✅ {name}" + (f" — {detail}" if detail else ""))
    else:
        FAIL += 1
        RESULTS.append(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


async def main():
    if not ADMIN_PASSWORD:
        raise RuntimeError("必须设置 E2E_ADMIN_PASSWORD")

    async with httpx.AsyncClient(base_url=BASE, timeout=15) as client:
        print("=" * 50)
        print("饭饭之交 闭环测试")
        print("=" * 50)

        # ========== 1. 认证模块 ==========
        print("\n[1] 认证模块")
        # 1.1 正确登录
        r = await client.post("/api/auth/login", json={
            "username": "admin", "password": ADMIN_PASSWORD
        })
        record(
            "正确密码登录并要求首次改密",
            r.status_code == 200
            and r.json().get("must_change_password") is True,
            f"status={r.status_code}",
        )
        token = r.json()["access_token"] if r.status_code == 200 else ""
        refresh = r.json().get("refresh_token", "") if r.status_code == 200 else ""
        headers = {"Authorization": f"Bearer {token}"}

        # 1.2 错误密码登录
        r = await client.post("/api/auth/login", json={
            "username": "admin", "password": "wrong"
        })
        record("错误密码被拒", r.status_code == 401)

        # 1.3 获取当前用户
        r = await client.get("/api/auth/me", headers=headers)
        record("获取当前用户", r.status_code == 200 and r.json()["username"] == "admin",
               r.json().get("username", ""))

        # 1.4 无 token 访问被拒
        r = await client.get("/api/auth/me")
        record("无 token 访问被拒", r.status_code in (401, 403))

        # 1.5 刷新 token 必须使用 JSON 请求体，查询参数不得继续兼容
        r = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
        record("JSON 请求体刷新 token", r.status_code == 200 and "access_token" in r.json())
        r = await client.post("/api/auth/refresh", params={"refresh_token": refresh})
        record("查询参数刷新 token 被拒", r.status_code == 422)

        # 1.6 首次改密前仅允许访问账户信息和改密接口
        r = await client.get("/api/orders", headers=headers)
        record("初始管理员改密前受限", r.status_code == 403)
        changed_admin_password = f"E2E-Admin-{uuid.uuid4().hex[:12]}"
        r = await client.put("/api/auth/password", headers=headers, json={
            "old_password": ADMIN_PASSWORD,
            "new_password": changed_admin_password,
        })
        record(
            "初始管理员完成强制改密",
            r.status_code == 200
            and r.json().get("must_change_password") is False,
        )
        changed_admin_token = r.json().get("access_token", "") if r.status_code == 200 else ""
        changed_admin_refresh = r.json().get("refresh_token", "") if r.status_code == 200 else ""
        r_old_access = await client.get("/api/auth/me", headers=headers)
        record("管理员改密后旧 access token 失效", r_old_access.status_code == 401)
        r_old_refresh = await client.post(
            "/api/auth/refresh", json={"refresh_token": refresh}
        )
        record("管理员改密后旧 refresh token 失效", r_old_refresh.status_code == 401)
        token = changed_admin_token
        refresh = changed_admin_refresh
        headers = {"Authorization": f"Bearer {token}"}

        # ========== 2. 系统配置 ==========
        print("\n[2] 系统配置")
        r = await client.get("/api/config")
        record("获取系统配置", r.status_code == 200 and "role_name_admin" in r.json(),
               str(r.json())[:80])

        # ========== 3. 分类 ==========
        print("\n[3] 分类管理")
        # 种子 6 个分类，用户可能自建更多，故用 >= 6
        r = await client.get("/api/categories", headers=headers)
        record("获取分类列表", r.status_code == 200 and len(r.json()) >= 6,
               f"共 {len(r.json())} 个")
        cat_id = r.json()[0]["id"]

        # 创建分类
        r = await client.post("/api/categories", headers=headers, json={
            "name": "测试分类", "sort_order": 99
        })
        record("创建分类", r.status_code == 201)
        if r.status_code == 201:
            new_cat_id = r.json()["id"]
            # 重复名称
            r2 = await client.post("/api/categories", headers=headers, json={
                "name": "测试分类", "sort_order": 1
            })
            record("重复分类名被拒", r2.status_code == 400)
            # 删除
            r3 = await client.delete(f"/api/categories/{new_cat_id}", headers=headers)
            record("删除分类", r3.status_code == 204)

        # ========== 4. 标签 ==========
        print("\n[4] 标签管理")
        r = await client.get("/api/tags", headers=headers)
        record("获取标签", r.status_code == 200 and len(r.json()) >= 3,
               f"共 {len(r.json())} 个")
        tag_name = r.json()[0]["name"]

        # ========== 5. 菜品管理 ==========
        print("\n[5] 菜品管理")
        # 5.1 创建菜品
        r = await client.post("/api/dishes", headers=headers, json={
            "name": "闭环测试菜",
            "category_id": cat_id,
            "description": "测试用\n第二行",
            "notes": "测试备注",
            "status": "active",
            "links": [{"url": "https://example.com", "title": "示例"}],
            "tag_names": [tag_name],
        })
        record("创建菜品", r.status_code == 201, f"status={r.status_code}")
        if r.status_code != 201:
            print("    菜品创建失败，终止后续测试")
            print(r.text)
            return PASS, FAIL, RESULTS
        dish_id = r.json()["id"]
        record("菜品含标签", len(r.json()["tags"]) == 1
               and r.json()["tags"][0]["name"] == tag_name)
        record("菜品含链接", len(r.json()["links"]) == 1)

        # 5.2 查询列表
        r = await client.get("/api/dishes", headers=headers)
        record("查询菜品列表", r.status_code == 200 and len(r.json()) >= 1)

        # 5.3 搜索（按菜名）
        r = await client.get("/api/dishes", headers=headers, params={"search": "闭环"})
        record("搜索菜品", r.status_code == 200 and len(r.json()) >= 1)

        # 5.3b 更新菜品标签：传入全新标签名，应自动创建并关联
        r = await client.put(f"/api/dishes/{dish_id}", headers=headers, json={
            "tag_names": [tag_name, "E2E自由标签"]
        })
        resp_names = {t["name"] for t in r.json()["tags"]} if r.status_code == 200 else set()
        r2 = await client.get("/api/tags", headers=headers)
        tag_created = any(t["name"] == "E2E自由标签" for t in r2.json())
        record("新标签自动创建",
               r.status_code == 200 and resp_names == {tag_name, "E2E自由标签"} and tag_created)

        # 5.3c 按标签名搜索
        r = await client.get("/api/dishes", headers=headers,
                             params={"search": "E2E自由标签"})
        record("按标签名搜索", r.status_code == 200 and len(r.json()) >= 1)

        # 5.4 查询详情
        r = await client.get(f"/api/dishes/{dish_id}", headers=headers)
        record("查询菜品详情", r.status_code == 200 and r.json()["name"] == "闭环测试菜")

        # 5.5 更新
        r = await client.put(f"/api/dishes/{dish_id}", headers=headers, json={
            "notes": "更新后的备注"
        })
        record("更新菜品", r.status_code == 200 and r.json()["notes"] == "更新后的备注")

        # 5.6 上传图片（构造一个简单的 PNG）
        png_bytes = make_png_bytes()
        files = [("files", ("test.png", io.BytesIO(png_bytes), "image/png"))]
        r = await client.post(f"/api/dishes/{dish_id}/images", headers=headers, files=files)
        record("上传图片", r.status_code == 200 and len(r.json()) == 1,
               f"status={r.status_code}")
        image_id = r.json()[0].get("image_path", "") if r.status_code == 200 else ""
        record("上传图片统一为 WebP", image_id.endswith(".webp"), image_id)

        # 5.7 上传超大文件被拒（构造 > 5MB）
        big = b"x" * (6 * 1024 * 1024)
        files = [("files", ("big.png", io.BytesIO(big), "image/png"))]
        r = await client.post(f"/api/dishes/{dish_id}/images", headers=headers, files=files)
        record("超大图片被拒", r.status_code == 400, f"status={r.status_code}")

        # 5.7b 损坏图片和扩展名伪装均不得落盘
        files_before = (
            {path for path in Path(UPLOAD_DIR).rglob("*") if path.is_file()}
            if UPLOAD_DIR else set()
        )
        disguised_jpeg = io.BytesIO()
        Image.new("RGB", (8, 8), "red").save(disguised_jpeg, format="JPEG")
        invalid_files = [
            ("broken.png", b"not-an-image", "image/png"),
            ("fake.png", disguised_jpeg.getvalue(), "image/png"),
        ]
        for filename, content, content_type in invalid_files:
            files = [("files", (filename, io.BytesIO(content), content_type))]
            r = await client.post(
                f"/api/dishes/{dish_id}/images",
                headers=headers,
                files=files,
            )
            record(f"无效图片 {filename} 被拒", r.status_code == 400)
        if UPLOAD_DIR:
            files_after = {path for path in Path(UPLOAD_DIR).rglob("*") if path.is_file()}
            record("无效图片不留残余文件", files_after == files_before)

        mixed_files_before = (
            {path for path in Path(UPLOAD_DIR).rglob("*") if path.is_file()}
            if UPLOAD_DIR else set()
        )
        mixed_files = [
            ("files", ("valid-first.png", io.BytesIO(make_png_bytes()), "image/png")),
            ("files", ("broken-second.png", io.BytesIO(b"not-an-image"), "image/png")),
        ]
        mixed_response = await client.post(
            f"/api/dishes/{dish_id}/images",
            headers=headers,
            files=mixed_files,
        )
        record("混合批量中的无效图片被拒", mixed_response.status_code == 400)
        if UPLOAD_DIR:
            mixed_files_after = {
                path for path in Path(UPLOAD_DIR).rglob("*") if path.is_file()
            }
            record("混合批量失败不留已处理图片", mixed_files_after == mixed_files_before)

        batch_files_before = (
            {path for path in Path(UPLOAD_DIR).rglob("*") if path.is_file()}
            if UPLOAD_DIR else set()
        )
        too_many_files = [
            (
                "files",
                (f"batch-{index}.png", io.BytesIO(make_png_bytes()), "image/png"),
            )
            for index in range(6)
        ]
        batch_response = await client.post(
            f"/api/dishes/{dish_id}/images",
            headers=headers,
            files=too_many_files,
        )
        record("单次上传超过五张图片被拒", batch_response.status_code == 400)
        if UPLOAD_DIR:
            batch_files_after = {
                path for path in Path(UPLOAD_DIR).rglob("*") if path.is_file()
            }
            record("超出批量数量限制不留文件", batch_files_after == batch_files_before)

        # 5.8 访问上传的图片
        if image_id:
            r = await client.get(f"/uploads/{image_id}")
            record("访问上传图片", r.status_code == 200, f"status={r.status_code}")

        # ========== 6. 订单流程 ==========
        print("\n[6] 订单流程")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        # 6.1 提交订单
        r = await client.post("/api/orders", headers=headers, json={
            "meal_date": tomorrow,
            "meal_type": "午餐",
            "note": "整单备注",
            "items": [{
                "dish_id": dish_id,
                "quantity": 2,
                "item_note": "少油",
            }],
        })
        record("提交订单", r.status_code == 201, f"status={r.status_code}")
        if r.status_code != 201:
            print("    订单创建失败:", r.text)
        order_id = r.json()["id"] if r.status_code == 201 else 0
        if r.status_code == 201:
            record("订单含菜品名", r.json()["items"][0]["dish_name"] == "闭环测试菜")

        # 6.2 空订单被拒
        r = await client.post("/api/orders", headers=headers, json={
            "meal_date": tomorrow, "meal_type": "午餐", "items": []
        })
        record("空订单被拒", r.status_code == 400)

        # 6.3 查询订单列表
        r = await client.get("/api/orders", headers=headers)
        record("查询订单列表", r.status_code == 200 and len(r.json()) >= 1)

        # 6.4 按状态筛选
        r = await client.get("/api/orders", headers=headers, params={"status_filter": "pending"})
        record("按状态筛选订单", r.status_code == 200)

        # 6.5 查询订单详情
        if order_id:
            r = await client.get(f"/api/orders/{order_id}", headers=headers)
            record("查询订单详情", r.status_code == 200)

        # ========== 7. 订单状态流转 ==========
        print("\n[7] 订单状态流转")
        if order_id:
            r = await client.patch(
                f"/api/orders/{order_id}", headers=headers, json={"status": "cooking"}
            )
            record("待处理订单不可跳到制作中", r.status_code == 400)
            r = await client.patch(
                f"/api/orders/{order_id}", headers=headers, json={"status": "pending"}
            )
            record("订单不可重复写入当前状态", r.status_code == 400)

            # pending → accepted
            r = await client.patch(f"/api/orders/{order_id}", headers=headers, json={"status": "accepted"})
            record("待处理→已接单", r.status_code == 200 and r.json()["status"] == "accepted")

            r = await client.patch(
                f"/api/orders/{order_id}", headers=headers, json={"status": "done"}
            )
            record("已接单订单不可跳到已完成", r.status_code == 400)
            r = await client.patch(
                f"/api/orders/{order_id}", headers=headers, json={"status": "pending"}
            )
            record("已接单订单不可回退", r.status_code == 400)

            # accepted → cooking
            r = await client.patch(f"/api/orders/{order_id}", headers=headers, json={"status": "cooking"})
            record("已接单→制作中", r.status_code == 200 and r.json()["status"] == "cooking")

            # cooking → done
            r = await client.patch(f"/api/orders/{order_id}", headers=headers, json={"status": "done"})
            record("制作中→已完成", r.status_code == 200 and r.json()["status"] == "done")

            # 已完成不能取消
            r = await client.delete(f"/api/orders/{order_id}", headers=headers)
            record("已完成订单不可取消", r.status_code == 400)
            r = await client.patch(
                f"/api/orders/{order_id}", headers=headers, json={"status": "accepted"}
            )
            record("已完成订单不可重开", r.status_code == 400)

        concurrent_order = await client.post("/api/orders", headers=headers, json={
            "meal_date": tomorrow,
            "meal_type": "午餐",
            "items": [{"dish_id": dish_id, "quantity": 1}],
        })
        concurrent_order_id = (
            concurrent_order.json().get("id")
            if concurrent_order.status_code == 201
            else None
        )
        record(
            "创建并发状态流转测试订单",
            concurrent_order_id is not None,
            f"status={concurrent_order.status_code}",
        )
        if concurrent_order_id:
            concurrent_results = await asyncio.gather(
                client.patch(
                    f"/api/orders/{concurrent_order_id}",
                    headers=headers,
                    json={"status": "accepted"},
                ),
                client.patch(
                    f"/api/orders/{concurrent_order_id}",
                    headers=headers,
                    json={"status": "accepted"},
                ),
            )
            record(
                "并发状态流转只能成功一次",
                sorted(result.status_code for result in concurrent_results)
                == [200, 400],
            )

        # ========== 8. 取消订单 ==========
        print("\n[8] 取消订单")
        # 新建一个待处理订单再取消
        cancel_id = None
        r = await client.post("/api/orders", headers=headers, json={
            "meal_date": tomorrow, "meal_type": "晚餐",
            "items": [{"dish_id": dish_id, "quantity": 1}],
        })
        if r.status_code == 201:
            cancel_id = r.json()["id"]
            r = await client.delete(f"/api/orders/{cancel_id}", headers=headers)
            record("取消待处理订单", r.status_code == 204)

        # ========== 8.5 菜品评价 ==========
        print("\n[8.5] 菜品评价")
        if order_id:
            # 已取消订单不可评价
            if cancel_id:
                r = await client.post(f"/api/orders/{cancel_id}/reviews", headers=headers, json={
                    "items": [{"dish_id": dish_id, "rating": 5}],
                })
                record("已取消订单不可评价", r.status_code == 400)
            # 当前 E2E 账号就是订单本人；非本人权限由后端单元测试覆盖。
            print("  - 非本人评价被拒：当前 E2E 账号为订单本人，跳过")

            # 评分越界被拒
            r = await client.post(f"/api/orders/{order_id}/reviews", headers=headers, json={
                "items": [{"dish_id": dish_id, "rating": 6}],
            })
            record("评分超出范围被拒", r.status_code == 422)

            # 不属于订单的菜品被拒
            r = await client.post(f"/api/orders/{order_id}/reviews", headers=headers, json={
                "items": [{"dish_id": 999999, "rating": 5}],
            })
            record("评价非订单菜品被拒", r.status_code == 400)

            # 正常提交评价
            r = await client.post(f"/api/orders/{order_id}/reviews", headers=headers, json={
                "items": [{"dish_id": dish_id, "rating": 5, "comment": "非常好吃"}],
            })
            submit_ok = (
                r.status_code == 200
                and not r.json().get("items", [{}])[0].get("updated", True)
            )
            record(
                "提交评价成功",
                submit_ok,
                f"status={r.status_code} body={r.text[:200]}" if not submit_ok else "",
            )

            # 查询菜品评分聚合
            r = await client.get(f"/api/dishes/{dish_id}")
            rating_ok = (
                r.status_code == 200
                and r.json().get("rating_count") == 1
                and abs((r.json().get("avg_rating") or 0) - 5.0) < 0.01
            )
            record("菜品详情含评分聚合", rating_ok,
                   f"avg={r.json().get('avg_rating')} count={r.json().get('rating_count')}")

            # 游客可读评价列表
            r = await client.get(f"/api/dishes/{dish_id}/reviews")
            list_ok = (
                r.status_code == 200
                and len(r.json()) == 1
                and r.json()[0]["comment"] == "非常好吃"
            )
            record("游客可读菜品评价列表", list_ok)

            # 修改评价（upsert）
            r = await client.post(f"/api/orders/{order_id}/reviews", headers=headers, json={
                "items": [{"dish_id": dish_id, "rating": 3, "comment": "改主意了"}],
            })
            update_ok = (
                r.status_code == 200
                and r.json()["items"][0]["updated"] is True
                and r.json()["items"][0]["rating"] == 3
            )
            record("重复提交更新评价", update_ok)

            # 均分随更新变化
            r = await client.get(f"/api/dishes/{dish_id}")
            record("均分随评价更新",
                   r.status_code == 200 and abs((r.json().get("avg_rating") or 0) - 3.0) < 0.01)

            # 订单评价回显
            r = await client.get(f"/api/orders/{order_id}/reviews", headers=headers)
            record("订单评价回显", r.status_code == 200 and len(r.json()) == 1)

            # 饲养员删除评价（当前用户是管理员，先验证普通用户被拒不可行，直接删除）
            review_id = (await client.get(
                f"/api/dishes/{dish_id}/reviews"
            )).json()[0]["id"]
            r_del = await client.delete(f"/api/reviews/{review_id}", headers=headers)
            record("饲养员/店长删除评价", r_del.status_code == 204)

            # 删除后评分清零
            r = await client.get(f"/api/dishes/{dish_id}")
            cleared_ok = (
                r.status_code == 200
                and r.json().get("rating_count") == 0
                and r.json().get("avg_rating") is None
            )
            record("删除后评分清空显示暂无评分", cleared_ok)

        # ========== 9. 推送 ==========
        print("\n[9] 推送通知")
        # 9.1 获取 VAPID 公钥（未配置应返回 enabled=false）
        r = await client.get("/api/push/vapid-public-key", headers=headers)
        record("获取 VAPID 状态", r.status_code == 200, f"enabled={r.json().get('enabled')}")

        # 9.2 测试推送（无订阅应返回 400）
        r = await client.post("/api/push/test", headers=headers, json={"message": "test"})
        record("无订阅时测试推送被拒", r.status_code == 400)

        # ========== 10. 用户管理与游客 ==========
        print("\n[10] 用户管理与游客")
        # 10.1 管理员创建用户
        r = await client.post("/api/users", headers=headers, json={
            "username": TEST_USERNAME, "password": "Test@123",
            "nickname": "E2E用户A", "is_feeder": False,
        })
        record("管理员创建用户", r.status_code == 201 and r.json()["is_admin"] is False)
        new_user_id = r.json()["id"] if r.status_code == 201 else 0

        # 10.2 重名被拒
        r2 = await client.post("/api/users", headers=headers, json={
            "username": TEST_USERNAME, "password": "Test@123"
        })
        record("创建用户重名被拒", r2.status_code == 400)

        # 10.3 新用户登录 must_change_password=true
        new_user_r = await client.post("/api/auth/login", json={
            "username": TEST_USERNAME, "password": "Test@123"
        })
        new_user_token = new_user_r.json()["access_token"] if new_user_r.status_code == 200 else ""
        new_user_refresh = new_user_r.json().get("refresh_token", "") if new_user_r.status_code == 200 else ""
        new_user_headers = {"Authorization": f"Bearer {new_user_token}"}
        record("新用户登录含强制改密",
               new_user_r.status_code == 200
               and new_user_r.json().get("must_change_password") is True)

        # 10.4 首次改密前不得使用普通业务接口
        r3 = await client.get("/api/orders", headers=new_user_headers)
        record("新用户改密前业务接口被拒", r3.status_code == 403)

        # 10.5 改密后清除标志
        r4 = await client.put("/api/auth/password", headers=new_user_headers, json={
            "old_password": "Test@123", "new_password": "NewPass@123"
        })
        record("新用户改密后清除强制改密标志",
               r4.status_code == 200 and r4.json().get("must_change_password") is False)
        changed_token = r4.json().get("access_token", "") if r4.status_code == 200 else ""
        changed_refresh = r4.json().get("refresh_token", "") if r4.status_code == 200 else ""
        changed_headers = {"Authorization": f"Bearer {changed_token}"}
        r_old_access = await client.get("/api/auth/me", headers=new_user_headers)
        record("改密后旧 access token 失效", r_old_access.status_code == 401)
        r_old_refresh = await client.post(
            "/api/auth/refresh", json={"refresh_token": new_user_refresh}
        )
        record("改密后旧 refresh token 失效", r_old_refresh.status_code == 401)
        r_new_access = await client.get("/api/auth/me", headers=changed_headers)
        record("改密后新 access token 可用", r_new_access.status_code == 200)
        new_user_headers = changed_headers
        new_user_refresh = changed_refresh

        r_role = await client.get("/api/users", headers=new_user_headers)
        record("非管理员访问用户管理被拒", r_role.status_code == 403)

        # 10.6 改昵称 + 预设头像
        r5 = await client.put("/api/auth/profile", headers=new_user_headers, json={
            "nickname": "改名A", "avatar_url": "/avatars/cat.png",
        })
        record("改昵称和预设头像",
               r5.status_code == 200
               and r5.json().get("nickname") == "改名A"
               and r5.json().get("avatar_url") == "/avatars/cat.png")

        for invalid_avatar in (
            "https://example.com/avatar.png",
            "/uploads/2026/08/other.webp",
            "2026/08/other.webp",
            "/avatars/not-a-preset.png",
        ):
            r_invalid_avatar = await client.put(
                "/api/auth/profile",
                headers=new_user_headers,
                json={"avatar_url": invalid_avatar},
            )
            record(f"非法头像路径被拒: {invalid_avatar}", r_invalid_avatar.status_code == 400)

        # 10.7 上传头像
        png_bytes = make_png_bytes()
        files = [("file", ("avatar.png", io.BytesIO(png_bytes), "image/png"))]
        r6 = await client.post("/api/auth/avatar", headers=new_user_headers, files=files)
        record("上传自定义头像",
               r6.status_code == 200 and bool(r6.json().get("avatar_url")))
        uploaded_avatar = r6.json().get("avatar_url") if r6.status_code == 200 else None
        keep_avatar = await client.put(
            "/api/auth/profile",
            headers=new_user_headers,
            json={"avatar_url": uploaded_avatar},
        )
        record(
            "可保留本人当前上传头像",
            keep_avatar.status_code == 200
            and keep_avatar.json().get("avatar_url") == uploaded_avatar,
        )
        clear_avatar = await client.put(
            "/api/auth/profile",
            headers=new_user_headers,
            json={"avatar_url": ""},
        )
        record(
            "可清空本人头像",
            clear_avatar.status_code == 200
            and clear_avatar.json().get("avatar_url") is None,
        )

        # 管理员不能取消他人的待处理订单，订单本人可以取消
        user_order = await client.post("/api/orders", headers=new_user_headers, json={
            "meal_date": tomorrow,
            "meal_type": "午餐",
            "items": [{"dish_id": dish_id, "quantity": 1}],
        })
        user_order_id = user_order.json().get("id") if user_order.status_code == 201 else None
        record("普通用户创建待处理订单", user_order_id is not None)
        if user_order_id:
            staff_cancel = await client.patch(
                f"/api/orders/{user_order_id}",
                headers=headers,
                json={"status": "cancelled"},
            )
            record("管理员不可取消他人订单", staff_cancel.status_code == 403)
            owner_cancel = await client.delete(
                f"/api/orders/{user_order_id}", headers=new_user_headers
            )
            record("订单本人可取消待处理订单", owner_cancel.status_code == 204)

        # 10.8 切换饲养员权限
        r7 = await client.put(f"/api/users/{new_user_id}/feeder",
                              headers=headers, json={"is_feeder": True})
        record("授予饲养员权限", r7.status_code == 200 and r7.json()["is_feeder"] is True)
        r8 = await client.put(f"/api/users/{new_user_id}/feeder",
                              headers=headers, json={"is_feeder": False})
        record("收回饲养员权限", r8.status_code == 200 and r8.json()["is_feeder"] is False)

        # 10.9 禁用账号
        r9 = await client.put(f"/api/users/{new_user_id}/status",
                              headers=headers, json={"is_active": False})
        record("禁用账号", r9.status_code == 200 and r9.json()["is_active"] is False)

        # 10.10 禁用账号登录 403
        r10 = await client.post("/api/auth/login", json={
            "username": TEST_USERNAME, "password": "NewPass@123"
        })
        record("禁用账号登录被拒", r10.status_code == 403)

        # 10.11 禁用账号旧 token 401
        r11 = await client.get("/api/auth/me", headers=new_user_headers)
        record("禁用账号旧 token 失效", r11.status_code == 401)

        r_reenable = await client.put(
            f"/api/users/{new_user_id}/status",
            headers=headers,
            json={"is_active": True},
        )
        record(
            "重新启用账号",
            r_reenable.status_code == 200
            and r_reenable.json().get("is_active") is True,
        )
        r_reenabled_access = await client.get("/api/auth/me", headers=new_user_headers)
        record("重新启用不恢复旧 access token", r_reenabled_access.status_code == 401)
        r_reenabled_refresh = await client.post(
            "/api/auth/refresh", json={"refresh_token": new_user_refresh}
        )
        record("重新启用不恢复旧 refresh token", r_reenabled_refresh.status_code == 401)

        # 10.12 禁用自己被拒（admin id=1 由 init_db 种子）
        r12 = await client.put("/api/users/1/status",
                               headers=headers, json={"is_active": False})
        record("禁用自己被拒", r12.status_code == 400)
        r_self_reset = await client.put(
            "/api/users/1/password",
            headers=headers,
            json={"password": "Bypass@123"},
        )
        record("管理员不能绕过旧密码重置自己", r_self_reset.status_code == 400)

        # 10.13 管理员重置密码
        r13 = await client.put(f"/api/users/{new_user_id}/password",
                               headers=headers, json={"password": "Reset@123"})
        record("管理员重置密码",
               r13.status_code == 200 and r13.json().get("must_change_password") is True)

        # 10.14 重置后登录强制改密
        r14 = await client.post("/api/auth/login", json={
            "username": TEST_USERNAME, "password": "Reset@123"
        })
        record("重置密码后强制改密",
               r14.status_code == 200 and r14.json().get("must_change_password") is True)
        reset_access = r14.json().get("access_token", "") if r14.status_code == 200 else ""
        reset_refresh = r14.json().get("refresh_token", "") if r14.status_code == 200 else ""
        r15 = await client.put(
            f"/api/users/{new_user_id}/password",
            headers=headers,
            json={"password": "ResetAgain@123"},
        )
        record("管理员再次重置密码", r15.status_code == 200)
        r16 = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {reset_access}"}
        )
        record("重置密码后旧 access token 失效", r16.status_code == 401)
        r17 = await client.post(
            "/api/auth/refresh", json={"refresh_token": reset_refresh}
        )
        record("重置密码后旧 refresh token 失效", r17.status_code == 401)

        # 10.15 游客（无 token）浏览
        async with httpx.AsyncClient(base_url=BASE, timeout=15) as guest:
            r = await guest.get("/api/dishes")
            record("游客无 token 获取 dishes", r.status_code == 200)
            r = await guest.get("/api/categories")
            record("游客获取 categories", r.status_code == 200)
            r = await guest.get("/api/tags")
            record("游客获取 tags", r.status_code == 200)
            r = await guest.post("/api/orders", json={
                "meal_date": tomorrow, "meal_type": "午餐",
                "items": [{"dish_id": dish_id, "quantity": 1}],
            })
            record("游客提交订单被拒", r.status_code in (401, 403))
            r = await guest.get("/api/orders")
            record("游客获取订单列表被拒", r.status_code in (401, 403))

        # 10.16 游客访问下架菜品 404
        r_inactive = await client.post("/api/dishes", headers=headers, json={
            "name": "下架测试E2E", "category_id": cat_id, "status": "inactive", "links": [],
        })
        inactive_id = r_inactive.json()["id"] if r_inactive.status_code == 201 else 0
        async with httpx.AsyncClient(base_url=BASE, timeout=15) as guest:
            r = await guest.get(f"/api/dishes/{inactive_id}")
            record("游客访问下架菜品 404", r.status_code == 404)

        # ========== 11. 清理 ==========
        print("\n[11] 清理测试数据")
        if order_id:
            r = await client.delete(f"/api/dishes/{dish_id}", headers=headers)
            record("删除测试菜品", r.status_code == 204)

        # 删除下架测试菜品
        if inactive_id:
            r = await client.delete(f"/api/dishes/{inactive_id}", headers=headers)
            record("删除下架测试菜品", r.status_code == 204)

        # 删除自动创建的测试标签
        r = await client.get("/api/tags", headers=headers)
        e2e_tag = next((t for t in r.json() if t["name"] == "E2E自由标签"), None)
        if e2e_tag:
            r = await client.delete(f"/api/tags/{e2e_tag['id']}", headers=headers)
            record("删除测试标签", r.status_code == 204)

        # ========== 汇总 ==========
        print("\n" + "=" * 50)
        print(f"测试结果：✅ 通过 {PASS} 项，❌ 失败 {FAIL} 项")
        print("=" * 50)
        print("\n详细结果：")
        for line in RESULTS:
            print(line)

        # 输出 markdown 结果供写入文件
        print("\n\n---MARKDOWN---")
        print(f"| 测试项 | 结果 | 说明 |\n|------|------|------|")
        # 重新生成表格
        return PASS, FAIL, RESULTS


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = asyncio.run(main())
    if not res or res[1] > 0:
        sys.exit(1)
