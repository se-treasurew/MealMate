import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DishCreateUploadSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "frontend/src/views/DishManage.vue").read_text(
            encoding="utf-8"
        )

    def test_create_form_exposes_five_image_uploader(self):
        self.assertIn('<div class="image-section">', self.source)
        self.assertNotIn(
            '<div v-if="editingDish?.id" class="image-section">', self.source
        )
        self.assertIn(':max-count="5"', self.source)

    def test_create_upload_failure_keeps_created_dish_for_retry(self):
        self.assertIn("editingDish.value = data", self.source)
        self.assertIn(
            "await uploadDishImages(data.id, files)", self.source
        )
        create_position = self.source.index("const { data } = await createDish(")
        promote_position = self.source.index("editingDish.value = data", create_position)
        upload_position = self.source.index(
            "await uploadDishImages(data.id, files)", promote_position
        )

        self.assertLess(create_position, promote_position)
        self.assertLess(promote_position, upload_position)
        self.assertIn("const saving = ref(false)", self.source)
        self.assertIn("if (saving.value) return", self.source)
        self.assertIn(':loading="saving"', self.source)
        self.assertIn(':disabled="saving"', self.source)
        self.assertIn(
            "菜品已创建，但图片上传失败，请重新选择图片", self.source
        )


class GithubE2EDependencyTests(unittest.TestCase):
    def test_httpx_is_installed_from_the_ci_requirements_file(self):
        requirements = (ROOT / "backend/requirements.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/release-check.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("httpx==0.28.1", requirements)
        self.assertIn(
            "python -m pip install -r backend/requirements.txt", workflow
        )
        self.assertIn("run: python run_e2e.py", workflow)


if __name__ == "__main__":
    unittest.main()
