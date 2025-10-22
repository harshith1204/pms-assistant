#!/usr/bin/env python3
"""
Extract UUIDs from the sample JSON collection files to help set environment variables.
This converts the Binary subtype 3 (Java legacy) format to standard UUID strings.
"""

import base64
import uuid
from pathlib import Path

def binary_to_uuid(base64_str: str) -> str:
    """Convert base64 Binary subtype 3 (Java legacy) to standard UUID string"""
    # Decode base64
    java_legacy_bytes = base64.b64decode(base64_str)
    
    # Convert from Java legacy format back to standard UUID
    # Reverse the first 3 components that were reversed during encoding
    standard_bytes = (
        java_legacy_bytes[3::-1] +      # time_low (4 bytes) reversed back
        java_legacy_bytes[5:3:-1] +     # time_mid (2 bytes) reversed back
        java_legacy_bytes[7:5:-1] +     # time_hi_and_version (2 bytes) reversed back
        java_legacy_bytes[8:]           # rest stays the same (8 bytes)
    )
    
    # Create UUID from bytes
    return str(uuid.UUID(bytes=standard_bytes))

# Extract from project file
print("=" * 80)
print("SAMPLE UUIDs FROM YOUR DATABASE")
print("=" * 80)
print("\nThese UUIDs are extracted from your sample collection files.")
print("Use them to set your environment variables for testing.\n")

print("📁 FROM PROJECT:")
# Business UUID from project
business_base64 = "TmBkxQU5Bx9oX+NCZRljrA=="
business_uuid = binary_to_uuid(business_base64)
print(f"   Business ID (Simpo.ai): {business_uuid}")
print(f"   → export BUSINESS_UUID='{business_uuid}'")

# Project UUID
project_base64 = "GERBNxWW/9lPeQtYn4LUpA=="
project_uuid = binary_to_uuid(project_base64)
print(f"\n   Project ID (gggg): {project_uuid}")

print("\n📁 FROM MEMBERS:")
# Staff UUID from members
staff_base64 = "zmTAgDeL/R7bNOMATJX9oQ=="
staff_uuid = binary_to_uuid(staff_base64)
print(f"   Staff ID (A Vikas): {staff_uuid}")
print(f"   → export MEMBER_UUID='{staff_uuid}'")

# Member's project UUID
member_project_base64 = "R0ueB9ZGHbgaMKTTNoC1kA=="
member_project_uuid = binary_to_uuid(member_project_base64)
print(f"\n   Member's Project ID (MCU): {member_project_uuid}")

print("\n" + "=" * 80)
print("💡 QUICK START:")
print("=" * 80)
print("\nCopy and paste these commands to set your environment variables:\n")
print(f"export BUSINESS_UUID='{business_uuid}'")
print(f"export MEMBER_UUID='{staff_uuid}'")
print("\nThen run: python test_business_member_filter.py")
print("=" * 80)
