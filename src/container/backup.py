import logging

from python_on_whales import docker

logger = logging.getLogger(__name__)


def create_tar_cmd(container):
    tar_cmd = ["tar", "-czf", f"/backup/{container.name}_volume_backup.tar.gz"]

    for volume in container.docker_volumes:
        tar_cmd.append(f"{volume}")
        print(volume)
        print(tar_cmd)

    for binding in container.docker_bindings:
        tar_cmd.append(f"{binding}")
        print(binding)
        print(tar_cmd)

    return tar_cmd


class Volume:

    @staticmethod
    def run_backup(container, backup_dir):
        print("CONTAINER SOURCE PATH: ", container.docker_volumes)
        print("CONTAINER SOURCE PATH: ", container.docker_bindings)
        print("BACKUP DIRECTORY: ", backup_dir.path)

        if not container.has_docker_volume and not container.has_docker_bindings:
            raise AssertionError("No volumes to backup")

        tar_cmd = create_tar_cmd(container)
        logger.debug(f"tar command: {tar_cmd}")

        # Todo: check issue when running on windows?
        volume_mapping = [{
            f"{backup_dir.path}:/backup"
            # f'{backup_dir.path.replace("_", "_")}:/backup'
        }]
        logger.debug(f"volume mapping for backup container: {volume_mapping}")

        try:
            tmp = docker.run("busybox:latest", tar_cmd, remove=True, volumes_from=container.name,
                             volumes=volume_mapping, detach=False)

        except Exception as err:
            logger.info(tmp)
            logger.error(err)
