"""Run full flow using SmartRegisterRunner, stop at producePdf for analysis."""
import sys, json, os
sys.path.insert(0, 'system')

from run_smart_register import SmartRegisterRunner

from pathlib import Path
case_path = Path("docs/case_兴裕为.json")
runner = SmartRegisterRunner(case_path=case_path)

# Must load case first
if not runner.load_case():
    print("Failed to load case!")
    sys.exit(1)

print(f"Case: {runner.case.get('phase1_check_name')}")
print(f"name_mark: {runner.case.get('name_mark')}")

# Run login + Phase 1 + Phase 2
result = runner.execute()
print(f"\nExit code: {result}")
