# #!/usr/bin/env python3
# """
# MongoDB ObjectId to UUID Converter

# Extracted from qdrant/insertdocs.py
# Converts MongoDB ObjectIds (including Binary subtype 3 UUIDs) to UUID format.

# Usage:
#     python mongo_to_uuid.py <mongodb_id>
#     python mongo_to_uuid.py 507f1f77bcf86cd799439011
#     python mongo_to_uuid.py "Binary.createFromBase64('pGeDu/TaBx8nH6ls4lsOuw==', 3)"
#     python mongo_to_uuid.py \\x03\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00
# """

import sys
import uuid
from bson.binary import Binary
# from bson.objectid import ObjectId


# def parse_binary_create_from_base64(input_str: str) -> str:
#     """
#     Parse MongoDB Binary.createFromBase64 format and convert to UUID.

#     Expected format: Binary.createFromBase64('base64_string', 3)

#     Args:
#         input_str: String in Binary.createFromBase64 format

#     Returns:
#         UUID string

#     Raises:
#         ValueError: If parsing fails or subtype is not 3
#     """
#     import re
#     import base64

#     # Match the pattern: Binary.createFromBase64('base64_string', 3)
#     pattern = r"Binary\.createFromBase64\('([^']+)', (\d+)\)"
#     match = re.match(pattern, input_str.strip())

#     if not match:
#         raise ValueError("Invalid Binary.createFromBase64 format. Expected: Binary.createFromBase64('base64_string', subtype)")

#     base64_data = match.group(1)
#     subtype = int(match.group(2))

#     if subtype != 3:
#         raise ValueError(f"Only Binary subtype 3 (UUID) is supported, got subtype {subtype}")

#     try:
#         # Decode base64 to binary
#         binary_data = base64.b64decode(base64_data)

#         # Verify it's 16 bytes (UUID length)
#         if len(binary_data) != 16:
#             raise ValueError(f"Invalid UUID length: expected 16 bytes, got {len(binary_data)}")

#         # Convert to UUID
#         return str(uuid.UUID(bytes=binary_data))

#     except Exception as e:
#         raise ValueError(f"Failed to decode base64 or convert to UUID: {e}")


# def normalize_mongo_id(mongo_id) -> str:
#     """
#     Convert MongoDB _id (ObjectId or Binary UUID) into a safe string.

#     Args:
#         mongo_id: MongoDB ObjectId, Binary UUID, or string representation

#     Returns:
#         str: Normalized string representation

#     Raises:
#         ValueError: If conversion fails
#     """
#     if isinstance(mongo_id, ObjectId):
#         return str(mongo_id)
#     elif isinstance(mongo_id, Binary) and mongo_id.subtype == 3:
#         # Binary subtype 3 is UUID
#         return str(uuid.UUID(bytes=mongo_id))
#     elif isinstance(mongo_id, str):
#         # Try to parse as Binary.createFromBase64 format first
#         try:
#             return parse_binary_create_from_base64(mongo_id)
#         except ValueError:
#             pass  # Not in Binary.createFromBase64 format, continue to other parsers

#         # Try to parse as ObjectId
#         try:
#             return str(ObjectId(mongo_id))
#         except Exception:
#             # Try to parse as Binary UUID
#             try:
#                 # Handle hex string representation of binary data
#                 if len(mongo_id) >= 6 and mongo_id.startswith('\\x03'):  # Binary UUID hex (subtype 3)
#                     # Remove \\x prefixes and convert
#                     hex_str = mongo_id.replace('\\x', '')
#                     # Remove the first 2 characters which represent the subtype (03)
#                     if len(hex_str) >= 32:  # UUID is 16 bytes = 32 hex chars
#                         uuid_hex = hex_str[2:34]  # Skip subtype, take 32 hex chars (16 bytes)
#                         binary_data = bytes.fromhex(uuid_hex)
#                         if len(binary_data) == 16:  # UUID length
#                             return str(uuid.UUID(bytes=binary_data))
#                 # Try direct hex conversion for 32-character hex strings (UUID)
#                 elif len(mongo_id) == 32:  # Direct UUID hex without subtype
#                     binary_data = bytes.fromhex(mongo_id)
#                     if len(binary_data) == 16:  # UUID length
#                         return str(uuid.UUID(bytes=binary_data))
#                 raise ValueError("Invalid UUID format")
#             except Exception as e:
#                 raise ValueError(f"Cannot parse as MongoDB ObjectId or UUID: {e}")
#     else:
#         return str(mongo_id)


# def convert_mongo_to_uuid(mongo_id_input):
#     """
#     Convert MongoDB ObjectId to UUID format.

#     Args:
#         mongo_id_input: MongoDB ObjectId in various formats:
#             - ObjectId object
#             - Binary UUID (subtype 3)
#             - Binary.createFromBase64('base64', 3) format
#             - String representation of ObjectId
#             - Binary hex string
#             - UUID hex string

#     Returns:
#         dict: Conversion result with original, converted, and type information
#     """
#     try:
#         normalized = normalize_mongo_id(mongo_id_input)

#         # Determine the type
#         if isinstance(mongo_id_input, ObjectId):
#             input_type = "ObjectId"
#         elif isinstance(mongo_id_input, Binary) and mongo_id_input.subtype == 3:
#             input_type = "Binary UUID (subtype 3)"
#         elif isinstance(mongo_id_input, str):
#             # Check for Binary.createFromBase64 format
#             if mongo_id_input.strip().startswith("Binary.createFromBase64"):
#                 input_type = "Binary.createFromBase64 (subtype 3)"
#             elif len(mongo_id_input) == 24:  # ObjectId length
#                 input_type = "ObjectId string"
#             elif len(mongo_id_input) == 32:  # Direct UUID hex
#                 input_type = "UUID hex string"
#             elif mongo_id_input.startswith('\\x03'):  # Binary hex format
#                 input_type = "Binary UUID hex string"
#             else:
#                 input_type = "UUID string"
#         else:
#             input_type = "Unknown"

#         # Check if it's a valid UUID format
#         is_uuid = False
#         try:
#             uuid.UUID(normalized)
#             is_uuid = True
#             uuid_type = "UUID"
#         except ValueError:
#             uuid_type = "ObjectId"

#         return {
#             "success": True,
#             "original_input": str(mongo_id_input),
#             "input_type": input_type,
#             "converted": normalized,
#             "output_type": uuid_type,
#             "is_uuid": is_uuid
#         }

#     except Exception as e:
#         return {
#             "success": False,
#             "original_input": str(mongo_id_input),
#             "error": str(e)
#         }




import re
import uuid
import base64
from bson.binary import Binary, UUID_SUBTYPE


def mongo_uuid_converter(input_str: str) -> str:
    """
    Converts between MongoDB Binary.createFromBase64(subtype 3) and UUID string formats.

    If input is a UUID string → returns Binary.createFromBase64('...', 3)
    If input is Binary.createFromBase64('...', 3) → returns UUID string

    Args:
        input_str (str): UUID string or Binary.createFromBase64('...', 3)

    Returns:
        str: Converted output (the opposite representation)
    """
    # Detect Binary.createFromBase64 input
    binary_pattern = r"Binary\.createFromBase64\('([^']+)',\s*3\)"
    match = re.match(binary_pattern, input_str.strip())

    try:
        if match:
            # --- Convert Binary → UUID ---
            base64_data = match.group(1)
            binary_data = base64.b64decode(base64_data)
            if len(binary_data) != 16:
                raise ValueError("Invalid binary UUID length")
            return str(uuid.UUID(bytes=binary_data))

        else:
            # --- Convert UUID → Binary ---
            uuid_obj = uuid.UUID(input_str)
            binary_uuid = Binary(uuid_obj.bytes, subtype=UUID_SUBTYPE)
            b64 = base64.b64encode(binary_uuid).decode()
            return f"Binary.createFromBase64('{b64}', 3)"

    except Exception as e:
        raise ValueError(f"Invalid input or conversion failed: {e}")



def main():
    """Command line interface for MongoDB to UUID conversion."""
    if len(sys.argv) != 2:
        print(__doc__)
        print("\nError: Please provide exactly one MongoDB ObjectId as argument.")
        print("\nExamples:")
        print("  python mongo_to_uuid.py 507f1f77bcf86cd799439011")
        print("  python mongo_to_uuid.py \\x03\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00")
        sys.exit(1)

    input_str = sys.argv[1]

    print("=" * 60)
    print("🔄 MongoDB ObjectId to UUID Converter")
    print("=" * 60)

    result = mongo_uuid_converter(input_str)
    print(result)
    # if result["success"]:
    #     print(f"📥 Input:  {result['original_input']}")
    #     print(f"🏷️  Type:   {result['input_type']}")
    #     print(f"📤 Output: {result['converted']}")
    #     print(f"✅ Type:   {result['output_type']}")

    #     if result['is_uuid']:
    #         print("🎯 Status: Successfully converted to UUID format!")
    #     else:
    #         print("ℹ️  Status: Converted to ObjectId string format")

    # else:
    #     print(f"❌ Conversion failed!")
    #     print(f"📥 Input:  {result['original_input']}")
    #     print(f"❌ Error:  {result['error']}")

    # print("=" * 60)


if __name__ == "__main__":
    main()
