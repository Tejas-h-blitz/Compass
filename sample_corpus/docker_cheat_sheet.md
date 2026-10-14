# Practical Docker Container Cheat Sheet

## Essential Image Commands
- `docker build -t app-name:v1 .` - Build container image using local Dockerfile.
- `docker images` - List locally cached container images.
- `docker rmi <image_id>` - Remove image from local store.

## Container Lifecycle Management
- `docker run -d -p 8080:80 --name web-app nginx:alpine` - Run container detached with port mapping.
- `docker ps -a` - Inspect status of all containers.
- `docker logs -f <container_name>` - Stream container standard output and error logs.
- `docker exec -it <container_name> /bin/sh` - Attach interactive shell to running container.

## Multi-stage Builds Best Practice
Always utilize multi-stage builds to compile binaries in an SDK environment and copy only the compiled artifact into a minimal scratch or alpine runtime image, reducing attack surface and image size.