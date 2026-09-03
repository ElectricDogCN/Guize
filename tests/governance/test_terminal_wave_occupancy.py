import copy
import importlib.util
import os
import tempfile
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
READINESS_SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-project-readiness.py")
FIXTURE_TEST = os.path.join(REPO_ROOT, "tests", "governance", "test_check_project_readiness.py")


def _load_module(name, path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Cannot load test dependency: {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


_readiness = _load_module("guize_project_readiness", READINESS_SCRIPT)
_fixture = _load_module("guize_project_readiness_fixture", FIXTURE_TEST)


class TestTerminalWaveOccupancy(unittest.TestCase):
    def setUp(self):
        self.harness = _fixture.TestProjectReadiness(methodName="test_valid_indexes_pass")

    def _clone_w1_task(
        self,
        plan,
        task_id,
        *,
        status="planned",
        risk_level="medium",
        output_path=None,
    ):
        source = next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")
        task = copy.deepcopy(source)
        task.update({
            "taskId": task_id,
            "title": f"Synthetic {task_id}",
            "status": status,
            "riskLevel": risk_level,
            "coordinationGroup": f"synthetic-{task_id.lower()}",
            "integrationOrder": 1 + sum(1 for item in plan["tasks"] if item.get("wave") == "W1"),
            "outputPaths": [output_path or f"specs/{task_id.lower()}/**"],
            "sharedPaths": [],
            "producesContracts": [f"{task_id}-CONTRACT"],
            "consumesContracts": [],
            "acceptanceIds": [],
            "pocIds": [],
            "issue": None,
            "branchPattern": f"chore/{task_id}-*",
            "exitGate": f"{task_id} synthetic readiness fixture is validated.",
        })
        plan["tasks"].append(task)
        return task

    def _run(self, requirements, modules, plan):
        with tempfile.TemporaryDirectory() as root:
            return self.harness._run(root, requirements, modules, plan)

    def test_only_terminal_states_release_wave_occupancy(self):
        tasks = [
            {"status": "planned"},
            {"status": "reserved"},
            {"status": "in_progress"},
            {"status": "review"},
            {"status": "integration"},
            {"status": "blocked"},
            {"status": "completed"},
            {"status": "cancelled"},
        ]
        occupying = _readiness.wave_occupying_tasks(tasks)
        self.assertEqual(
            [task["status"] for task in occupying],
            ["planned", "reserved", "in_progress", "review", "integration", "blocked"],
        )

    def test_completed_history_releases_slot_for_active_and_planned_tasks(self):
        requirements, modules, plan = self.harness._documents()
        historical = next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")
        historical["status"] = "completed"
        plan["waves"][0]["maxConcurrent"] = 2
        self._clone_w1_task(
            plan,
            "GZ-102",
            status="in_progress",
            output_path=historical["outputPaths"][0],
        )
        self._clone_w1_task(plan, "GZ-103", status="planned")

        result = self._run(requirements, modules, plan)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cancelled_history_releases_capacity_and_path_claims(self):
        requirements, modules, plan = self.harness._documents()
        historical = next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")
        historical["status"] = "cancelled"
        self._clone_w1_task(
            plan,
            "GZ-102",
            output_path=historical["outputPaths"][0],
        )

        result = self._run(requirements, modules, plan)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_third_non_terminal_task_still_fails_capacity(self):
        requirements, modules, plan = self.harness._documents()
        next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")["status"] = "completed"
        plan["waves"][0]["maxConcurrent"] = 2
        self._clone_w1_task(plan, "GZ-102", status="planned")
        self._clone_w1_task(plan, "GZ-103", status="reserved")
        self._clone_w1_task(plan, "GZ-104", status="in_progress")

        result = self._run(requirements, modules, plan)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Wave W1 exceeds concurrent task capacity", result.stdout)

    def test_non_terminal_high_risk_limit_remains_fail_closed(self):
        requirements, modules, plan = self.harness._documents()
        next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")["status"] = "completed"
        plan["waves"][0]["maxConcurrent"] = 3
        self._clone_w1_task(plan, "GZ-102", status="planned", risk_level="high")
        self._clone_w1_task(plan, "GZ-103", status="reserved", risk_level="high")

        result = self._run(requirements, modules, plan)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Wave W1 exceeds high-risk task capacity", result.stdout)

    def test_non_terminal_critical_task_still_requires_standalone_wave(self):
        requirements, modules, plan = self.harness._documents()
        next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")["status"] = "completed"
        plan["waves"][0]["maxConcurrent"] = 3
        self._clone_w1_task(plan, "GZ-102", status="planned", risk_level="critical")
        self._clone_w1_task(plan, "GZ-103", status="reserved", risk_level="medium")

        result = self._run(requirements, modules, plan)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Wave W1 contains a critical task that is not standalone", result.stdout)

    def test_non_terminal_path_conflict_remains_fail_closed(self):
        requirements, modules, plan = self.harness._documents()
        next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")["status"] = "completed"
        plan["waves"][0]["maxConcurrent"] = 2
        self._clone_w1_task(plan, "GZ-102", status="planned", output_path="specs/shared/**")
        self._clone_w1_task(plan, "GZ-103", status="reserved", output_path="specs/shared/**")

        result = self._run(requirements, modules, plan)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Wave W1 output path conflict", result.stdout)

    def test_terminal_task_remains_in_dependency_validation(self):
        requirements, modules, plan = self.harness._documents()
        historical = next(task for task in plan["tasks"] if task["taskId"] == "GZ-101")
        historical["status"] = "completed"
        historical["dependsOn"] = ["GZ-999"]
        self._clone_w1_task(plan, "GZ-102", status="planned")

        result = self._run(requirements, modules, plan)

        self.assertEqual(result.returncode, 1)
        self.assertIn("Planned task GZ-101 depends on unknown task GZ-999", result.stdout)


if __name__ == "__main__":
    unittest.main()
