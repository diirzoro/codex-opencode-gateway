"""Fast unit checks for Smart Preview metadata; runs without worker or npm."""
import unittest

from app.services.preview_scheduling import classify, idle_expired, plan_pools, DYNAMIC_IDLE_TIMEOUT_SECONDS


class SmartPreviewClassificationTests(unittest.TestCase):
    def test_html_needs_no_dynamic_slot(self):
        result = classify({"framework": "html"})
        self.assertEqual(result["resource_tier"], "static")
        self.assertEqual(result["strategy"], "serve_static")
        self.assertFalse(result["consumes_dynamic_slot_now"])

    def test_static_capable_javascript_needs_isolated_build(self):
        for framework in ("vite", "react", "vue", "angular", "svelte"):
            with self.subTest(framework=framework):
                result = classify({"framework": framework})
                self.assertEqual(result["resource_tier"], "build")
                self.assertEqual(result["strategy"], "isolated_build_required")
                self.assertFalse(result["continuous_runtime_potentially_required"])

    def test_dynamic_projects_require_isolation(self):
        for framework in ("node", "django", "python", "laravel", "nuxt"):
            with self.subTest(framework=framework):
                self.assertTrue(classify({"framework": framework})["continuous_runtime_potentially_required"])

    def test_nextjs_never_assumed_static(self):
        result = classify({"framework": "nextjs"})
        self.assertEqual(result["resource_tier"], "conditional")
        self.assertEqual(result["strategy"], "inspect_next_output_in_worker")

    def test_pool_is_logical_not_active_sessions(self):
        result = classify({"framework": "html"})
        self.assertEqual(result["pool_target_users"], 50)
        self.assertEqual(result["pool_max_users"], 100)
        self.assertFalse(result["consumes_dynamic_slot_now"])

    def test_dynamic_idle_requires_explicit_restart(self):
        state = classify({"framework": "python"})
        self.assertEqual(state["dynamic_idle_timeout_seconds"], 300)
        self.assertTrue(state["idle_restart_requires_explicit_user_request"])
        self.assertEqual(DYNAMIC_IDLE_TIMEOUT_SECONDS, 300)
        self.assertFalse(idle_expired(last_activity_monotonic=10.0, now_monotonic=309.9))
        self.assertTrue(idle_expired(last_activity_monotonic=10.0, now_monotonic=310.0))

    def test_logical_pool_boundaries(self):
        self.assertEqual(plan_pools(0)["logical_pools_required"], 0)
        self.assertEqual(plan_pools(50)["logical_pools_required"], 1)
        self.assertEqual(plan_pools(51)["logical_pools_required"], 2)
        self.assertEqual(plan_pools(100, users_per_pool=100)["logical_pools_required"], 1)
        self.assertFalse(plan_pools(51)["auto_provision_enabled"])
        self.assertIsNone(plan_pools(51)["provisioned_pools"])

    def test_pool_inputs_reject_invalid_values(self):
        for count in (-1, True, 3.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                plan_pools(count)
        for size in (0, 101, True):
            with self.subTest(size=size), self.assertRaises(ValueError):
                plan_pools(1, users_per_pool=size)

    def test_unknown_fails_closed(self):
        result = classify({"framework": "something-new"})
        self.assertEqual(result["resource_tier"], "unsupported")
        self.assertEqual(result["strategy"], "diagnose")


if __name__ == "__main__":
    unittest.main()
