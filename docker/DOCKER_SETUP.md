Docker Setup & Fast-build Guide (Youtube Channel Summarizer)

This repo uses a 5-layer Docker architecture to make iterative development fast and predictable:

Layers (top → bottom)

*   **service_code** — service-specific code + API files (rebuilt most often)
*   **base_code** — shared src/, docs copied into image (rebuilt when shared code changes)
*   **service_requirements** — per-service pip packages (rebuilt when a service needs new deps)
*   **base_requirements** — shared Python libs (rebuilt when a global dependency changes)
*   **base_linux** — OS / apt packages / build tools (rarely changes)

## WHY stages (short)

Docker `FROM` references are resolved at build time. If a child image is built before its parent image exists locally, Docker will try to pull it from a registry (→ pull access denied or similar).

Compose may attempt builds in parallel; that can cause child builds to try to use an image that hasn’t been built yet.

Staging ensures parents exist first, and lets Docker caching do the rest: change code → rebuild only the code layer; change a single service dependency → rebuild only that service’s requirement layer + its code.

## First-time (full) build — safe ordered sequence

Run these in order (explicit, guaranteed):

### Build base linux (apt packages, compilers):

```bash
docker compose -f docker-compose.environment.yml build base_linux
```

### Build base requirements (Python + shared libs):

```bash
docker compose -f docker-compose.environment.yml build base_requirements
```

### Build all service requirements (per-service pip installs). Since base_requirements exists locally now, building them all is safe:

```bash
docker compose -f docker-compose.environment.yml build 
```

(You can build them all at once — the important thing is that `base_requirements` already exists locally.)

### Build base_code (copies src/, docs into the base image used by code images):

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build base_code
```

### Build all service code images:

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build
```

### Run everything:

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml up
```

**Note:** `-f ...environment.yml -f ...code.yml` combines environment + code files so the code images can resolve the environment images defined in the environment file.

## Why both compose files are needed for code images

Even though the `service_code` images are only defined in `docker-compose.code.yml`, they inherit from images defined in `docker-compose.environment.yml` (e.g. `base_code`, `*_service_requirements`).
If you run `docker compose -f docker-compose.code.yml build` alone, Docker will try to resolve the parent images by pulling them from a registry (since they aren’t defined in that file).
By combining the two files with:

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build
```

Compose knows about both the parent (environment) and child (code) services, so it can resolve local images correctly.


## Quick note about parallel builds and FROM

If you try `docker compose -f environment -f code build` straight away, Compose may attempt to build multiple images in parallel and child builds will try to `FROM youtube-channel-summarizer-base-code:latest` (or other local image names) before those base images exist locally — causing Docker to try pulling them from a registry. That’s why the ordered sequence above is reliable.

If you prefer a single command and want Compose to build sequentially, you can use:

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build --no-parallel
```

But explicit step-by-step is simpler and less error-prone.

## Update flows — rebuild only what’s necessary

(Each block explains what must be rebuilt and why.)

### A. Add a new global Python library (affects all services)

*   **What to rebuild:** `base_requirements` and then all `*_service_requirements`.
*   **Why:** global libs are installed in `base_requirements`; service-specific images depend on it.

**Commands:**

```bash
# rebuild base requirements (force fresh)
docker compose -f docker-compose.environment.yml build --no-cache base_requirements

# rebuild all service requirements so they pick up the updated base
docker compose -f docker-compose.environment.yml build
```

(After that, rebuild code images if their runtime images need to be re-created; see `base_code` step below if you rely on `base_code`.)

### B. Add a new requirement only for one service (e.g. summarization)

*   **What to rebuild:** only that service's `*_requirements` image, then that service's code image.
*   **Why:** only that service needs the new deps.

**Commands:**

```bash
# rebuild just the summarization service requirements (fresh)
docker compose -f docker-compose.environment.yml build --no-cache summarization_service_requirements

# then rebuild the summarization service code image so it uses the updated requirements image
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build summarization_service
```

(No other services are rebuilt.)

### C. Change shared code in `src/` (`base_code`)

*   **What to rebuild:** `base_code` and then all service code images.
*   **Why:** `base_code` includes shared `src/`; service images copy or inherit from it.

**Commands:**

```bash
# rebuild base_code first (fresh so new src is baked in)
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build --no-cache base_code

# then rebuild all service code images (fast if requirements images already exist)
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build
```

### D. Change only one service’s source files (fast path)

*   **What to rebuild:** that service’s `service_code` image only.
*   **Why:** code layer is last step; pip installs and base layers are unchanged and cached.

**Command:**

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build summarization_service
```

(You do NOT need `--no-cache`. Docker will reuse cached parent layers and only rebuild the changed code layer.)

## How to rebuild all code images (without touching environment layers)

If you want to rebuild every code image (no manual listing), and you already have the environment images built locally (`base_linux`, `base_requirements`, `service_requirements`, `base_code`), do:

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml \
  build $(docker compose -f docker-compose.code.yml config --services)
```

If you want to force rebuilding code images from scratch (no cache on the code images only):

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml \
  build --no-cache $(docker compose -f docker-compose.code.yml config --services)
```

If it doesn't build only the code services enter ctrl+c to stop and try again with manually writing the services names.

**Important precondition:** the service requirements images referenced by your code Dockerfiles must already exist locally. If they do not, Docker will attempt to pull those image names (or build them if you included them in the command). If you see pip installs running, it means you included requirement-image builds in the run or they were missing and Docker rebuilt them.

## Why `--no-cache` must be used carefully

`--no-cache` forces all layers in the image being built to be re-executed. If you pass `--no-cache` while building a service requirements image, pip installs will run again (slow).

For code-only changes, do not use `--no-cache` on the requirements images: only build the `service_code` image for fast iteration.

## Checking files in images/containers (debugging missing-files)

If a service reports a missing file (e.g. missing `/app/apis/summarization_api.yaml`), verify:

### Inspect the image contents (no container needed):

```bash
docker run --rm -it <image_name>:latest ls -la /app/apis
docker run --rm -it <image_name>:latest cat /app/apis/summarization_api.yaml
```

### Inspect a running container:

```bash
docker ps -a                      # find container name
docker exec -it <container_name> ls -la /app/apis
docker exec -it <container_name> cat /app/apis/summarization_api.yaml
```

If file is missing: check the `COPY` path in the Dockerfile and confirm the file exists in the build context (the folder set as `context:` in `docker-compose.yml`).

## Practical examples — short recap

### Add requirement to `summarization_service`
Rebuild only that service's reqs + code:

```bash
docker compose -f docker-compose.environment.yml build --no-cache summarization_service_requirements
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build summarization_service
```

### Change one line in `src/services/summarization_service/app.py`
Rebuild only that service code:

```bash
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build summarization_service
```

### Change `requirements.txt` in `base_requirements`
Rebuild `base_requirements` then all `service_requirements`:

```bash
docker compose -f docker-compose.environment.yml build --no-cache base_requirements
docker compose -f docker-compose.environment.yml build
```

### First-time full build (ordered, reliable):

```bash
docker compose -f docker-compose.environment.yml build base_linux
docker compose -f docker-compose.environment.yml build base_requirements
docker compose -f docker-compose.environment.yml build 
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build --no-cache base_code
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml build
docker compose -f docker-compose.environment.yml -f docker-compose.code.yml up
```

## Final tips

*   Keep `pip install` only in the `service_requirements` Dockerfiles. Service code Dockerfiles should only copy code and API files and set `ENV PYTHONPATH=/app` (or use `python -m`), not install packages. That guarantees code builds stay fast.

*   If you ever see large `pip install`s while building code images — you’re either building the requirements images too, or those images didn’t exist locally. Build the requirement images first.

*   Keep your `apis/` (or `documentation/`) files inside the build context (repo root) and copy them into `/app/apis` in the Dockerfile — then reference `/app/apis/...` in code.