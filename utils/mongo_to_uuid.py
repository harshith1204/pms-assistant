"""MongoDB ObjectId to UUID converter."""

import base64
import logging
import re
import sys
import uuid
from bson.binary import Binary, UuidRepresentation


logger = logging.getLogger(__name__)


def mongo_uuid_converter(input_str: str) -> str:
    """Convert between MongoDB Binary.createFromBase64(subtype 3) and UUID strings."""
    pattern = r"Binary\.createFromBase64\('([^']+)',\s*3\)"
    match = re.match(pattern, input_str.strip())

    try:
        if match:
            base64_data = match.group(1)
            binary_data = base64.b64decode(base64_data)
            if len(binary_data) != 16:
                raise ValueError("Invalid binary UUID length")
            binary = Binary(binary_data, subtype=3)
            return str(binary.as_uuid(uuid_representation=UuidRepresentation.JAVA_LEGACY))

        uuid_obj = uuid.UUID(input_str)
        binary_uuid = Binary.from_uuid(uuid_obj, uuid_representation=UuidRepresentation.JAVA_LEGACY)
        encoded = base64.b64encode(binary_uuid).decode()
        return f"Binary.createFromBase64('{encoded}', 3)"

    except Exception as exc:
        raise ValueError(f"Invalid input or conversion failed: {exc}") from exc


def main() -> None:
    if len(sys.argv) != 2:
        logger.error("Expected exactly one MongoDB ObjectId or UUID argument.")
        sys.exit(1)

    input_str = sys.argv[1]

    try:
        result = mongo_uuid_converter(input_str)
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)

    sys.stdout.write(f"{result}\n")


if __name__ == "__main__":
    main()
