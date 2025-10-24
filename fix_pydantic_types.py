#!/usr/bin/env python3
"""
Script to fix all remaining Pydantic type definitions.
Converts them to use the proper decorator pattern with experimental pydantic.
"""
import re
from pathlib import Path

# Files to fix
files_to_fix = [
    "app/usecases/commands/register_site_to_trial/types.py",
    "app/usecases/workflows/onboard_trial_sync/types.py",
    "app/usecases/workflows/onboard_trial_async/types.py",
]

for file_path in files_to_fix:
    path = Path(file_path)
    content = path.read_text()

    # Fix RegisterSiteToTrialInput
    if "RegisterSiteToTrialInput" in content:
        content = re.sub(
            r'class RegisterSiteToTrialInput\(BaseModel\):',
            'class RegisterSiteToTrialInputModel(BaseModel):',
            content
        )
        content = re.sub(
            r'RegisterSiteToTrialInputGQL = pydantic_input\(RegisterSiteToTrialInput\)',
            '''@pydantic_input(model=RegisterSiteToTrialInputModel, all_fields=True)
class RegisterSiteToTrialInput:
    """GraphQL input for registering a site to a trial (backed by Pydantic)."""
    pass''',
            content
        )

    # Fix SiteInput
    if "class SiteInput(BaseModel):" in content and "SiteInputGQL" in content:
        content = re.sub(
            r'class SiteInput\(BaseModel\):',
            'class SiteInputModel(BaseModel):',
            content
        )
        content = re.sub(
            r'# GraphQL input type for SiteInput\nSiteInputGQL = pydantic_input\(SiteInput\)',
            '''# GraphQL input type for SiteInput
@pydantic_input(model=SiteInputModel, all_fields=True)
class SiteInput:
    """GraphQL input for site (backed by Pydantic)."""
    pass''',
            content
        )
        # Fix references in OnboardTrialSyncInput
        content = re.sub(
            r'sites: list\[SiteInput\]',
            'sites: list[SiteInputModel]',
            content
        )

    # Fix OnboardTrialSyncInput
    if "class OnboardTrialSyncInput(BaseModel):" in content:
        content = re.sub(
            r'class OnboardTrialSyncInput\(BaseModel\):',
            'class OnboardTrialSyncInputModel(BaseModel):',
            content
        )
        content = re.sub(
            r'# GraphQL input type for OnboardTrialSyncInput\nOnboardTrialSyncInputGQL = pydantic_input\(OnboardTrialSyncInput\)',
            '''# GraphQL input type for OnboardTrialSyncInput
@pydantic_input(model=OnboardTrialSyncInputModel, all_fields=True)
class OnboardTrialSyncInput:
    """GraphQL input for synchronous trial onboarding (backed by Pydantic)."""
    pass''',
            content
        )

    # Fix OnboardTrialAsyncInput
    if "class OnboardTrialAsyncInput(BaseModel):" in content:
        content = re.sub(
            r'class OnboardTrialAsyncInput\(BaseModel\):',
            'class OnboardTrialAsyncInputModel(BaseModel):',
            content
        )
        content = re.sub(
            r'# GraphQL input type for OnboardTrialAsyncInput\nOnboardTrialAsyncInputGQL = pydantic_input\(OnboardTrialAsyncInput\)',
            '''# GraphQL input type for OnboardTrialAsyncInput
@pydantic_input(model=OnboardTrialAsyncInputModel, all_fields=True)
class OnboardTrialAsyncInput:
    """GraphQL input for asynchronous trial onboarding (backed by Pydantic)."""
    pass''',
            content
        )
        # Fix import
        content = re.sub(
            r'from app\.usecases\.workflows\.onboard_trial_sync\.types import SiteInput, SiteInputGQL',
            'from app.usecases.workflows.onboard_trial_sync.types import SiteInputModel',
            content
        )
        # Fix usage
        content = re.sub(
            r'sites: list\[SiteInput\]',
            'sites: list[SiteInputModel]',
            content
        )

    path.write_text(content)
    print(f"✓ Fixed {file_path}")

print("\n✓ All types fixed!")
