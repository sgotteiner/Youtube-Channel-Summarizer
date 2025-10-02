# Docker Architecture Refactoring

This document outlines the refactoring of the Docker setup for the YouTube Channel Summarizer project. The primary goal of this refactoring was to improve build times, reduce image sizes, and enhance maintainability by leveraging Docker's layering and caching mechanisms.

## Problems with the Previous Approach

The original `docker-compose.yml` file used a single build context (`build: .`) for all services. This meant that while there was only one Dockerfile, it was used to build a separate image for each service. This approach created several inefficiencies:

*   **Extremely Slow Builds:** The primary issue was the repeated installation of all dependencies for every single service. The `pip install -r requirements.txt` command ran for each service, causing the same packages to be downloaded and installed multiple times, which dramatically slowed down the build process.
*   **Inefficient Caching:** A code change in any service could invalidate the cache for other services, as they all shared the same build context. This often led to unnecessary and time-consuming rebuilds of unchanged services.
*   **Poor Maintainability:** A single, large `requirements.txt` file for the entire project made it difficult to track which dependencies were needed by which service. This increased maintenance overhead and the risk of dependency conflicts.
*   **Larger Total Image Size:** Although layers were shared to some extent, the final set of images on disk was larger than necessary due to the repeated dependency installation steps in different image build processes.

## The New Layered Architecture

The new architecture solves these problems by creating a dedicated, shared base image that contains all common dependencies. Service images are then built on top of this base image.

```
  +--------------------------------------------------+
  |   Base Image: youtube-channel-summarizer-base    |
  | (Python 3.12 + All Common Dependencies)          |
  +--------------------------------------------------+
                         ^
                         |
  +----------------------+----------------------+
  |                      |                      |
+------------------+   +------------------+   +------------------+
| Service Image A  |   | Service Image B  |   | Service Image C  |
| (FROM base)      |   | (FROM base)      |   | (FROM base)      |
| (+ Service A Code) |   | (+ Service B Code) |   | (+ Service C Code) |
+------------------+   +------------------+   +------------------+
```

### 1. Base Image

A new `base` image (`youtube-channel-summarizer-base:latest`) is defined in `base/Dockerfile`. This image contains:
*   Python 3.12.
*   Build tools necessary for packages like `psycopg2`.
*   All Python dependencies required by any service, installed from `base/requirements.txt`.

This base image is built only once.

### 2. Service Images

Each service now has its own dedicated `Dockerfile` (e.g., `src/services/orchestrator_service/Dockerfile`). This file is very simple:
*   It starts from the `youtube-channel-summarizer-base` image.
*   It copies only its own source code into the image.
*   It defines the `CMD` to run the service.

Each service also has its own `requirements.txt` file. For now, these are empty, but they can be used in the future to install service-specific dependencies that are not needed in the base image.

## Benefits of the New Architecture

This layered approach provides significant benefits:

*   **Dramatically Faster Builds:** Dependencies are installed only once when the base image is built. Since the base image is cached, subsequent builds are incredibly fast, as Docker only needs to copy the service's source code—a much quicker operation.
*   **Effective Caching:** Docker's layer caching is now used properly. The base image is only rebuilt if `base/requirements.txt` changes. A code change in one service will only trigger a rebuild of that specific service's image, leaving all others untouched.
*   **Reduced Image Size:** By sharing the large dependency layer across all services, the total disk space required for the project's images is significantly reduced.
*   **Improved Maintainability:** Common dependencies are managed in a single, central location (`base/requirements.txt`). Service-specific dependencies can be isolated in their respective `requirements.txt` files, providing a clear and clean separation of concerns.
*   **Consistency:** All services run on the exact same base image, ensuring a consistent and stable environment across the entire project.