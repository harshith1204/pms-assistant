set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ACR_REGISTRY="${ACR_REGISTRY:-${1:-aiplanboard.azurecr.io}}"
IMAGE_TAG="${IMAGE_TAG:-${2:-latest}}"
IMAGE_PREFIX="${IMAGE_PREFIX:-aiplanboard}"

# Validate ACR registry name
if [ -z "$ACR_REGISTRY" ]; then
    echo -e "${RED}Error: ACR registry name is required${NC}"
    echo "Usage: $0 <acr-registry-name> [tag]"
    echo "   or: ACR_REGISTRY=<registry-name> IMAGE_TAG=<tag> $0"
    echo ""
    echo "Example: $0 aiplanboard.azurecr.io v1.0.0"
    exit 1
fi

# Remove trailing slash if present
ACR_REGISTRY="${ACR_REGISTRY%/}"

echo -e "${GREEN}Building and pushing images to ACR: ${ACR_REGISTRY}${NC}"
echo -e "${YELLOW}Tag: ${IMAGE_TAG}${NC}"
echo ""

# Login to ACR (if not already logged in)
echo -e "${YELLOW}Logging in to ACR...${NC}"
az acr login --name "${ACR_REGISTRY%.azurecr.io}" || {
    echo -e "${RED}Failed to login to ACR. Make sure Azure CLI is installed and you're logged in.${NC}"
    echo "Run: az login"
    exit 1
}

# Function to build and push an image
build_and_push() {
    local service_name=$1
    local dockerfile_path=$2
    local context_path=$3
    
    local image_name="${ACR_REGISTRY}/${IMAGE_PREFIX}-${service_name}:${IMAGE_TAG}"
    local image_name_latest="${ACR_REGISTRY}/${IMAGE_PREFIX}-${service_name}:latest"
    
    echo -e "${GREEN}Building ${service_name}...${NC}"
    docker build -t "${image_name}" -t "${image_name_latest}" -f "${dockerfile_path}" "${context_path}" || {
        echo -e "${RED}Failed to build ${service_name}${NC}"
        exit 1
    }
    
    echo -e "${GREEN}Pushing ${service_name}...${NC}"
    docker push "${image_name}" || {
        echo -e "${RED}Failed to push ${service_name}${NC}"
        exit 1
    }
    
    docker push "${image_name_latest}" || {
        echo -e "${YELLOW}Warning: Failed to push latest tag for ${service_name}${NC}"
    }
    
    echo -e "${GREEN}✓ Successfully built and pushed ${service_name}${NC}"
    echo ""
}

# Build and push all services
echo -e "${YELLOW}Starting build process...${NC}"
echo ""

# Backend (agent)
build_and_push "backend" "agent/Dockerfile" "."

# Embedding service
build_and_push "embedding" "embedding_service/Dockerfile" "."

# SPLADE service
build_and_push "splade" "splade_service/Dockerfile" "."

# Consumer service
build_and_push "consumer" "data-sync/consumer/Dockerfile" "."

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All images built and pushed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Images pushed to:"
echo "  - ${ACR_REGISTRY}/${IMAGE_PREFIX}-backend:${IMAGE_TAG}"
echo "  - ${ACR_REGISTRY}/${IMAGE_PREFIX}-embedding:${IMAGE_TAG}"
echo "  - ${ACR_REGISTRY}/${IMAGE_PREFIX}-splade:${IMAGE_TAG}"
echo "  - ${ACR_REGISTRY}/${IMAGE_PREFIX}-consumer:${IMAGE_TAG}"
echo ""
echo "To use these images, set ACR_REGISTRY and run:"
echo "  ACR_REGISTRY=${ACR_REGISTRY} docker-compose up"

