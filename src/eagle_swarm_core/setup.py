from glob import glob

from setuptools import find_packages, setup

package_name = "eagle_swarm_core"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Haya Medhat Abdelhamid",
    maintainer_email="haya@example.com",
    description="EAGLE SWARM distributed coordination core.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "agent=eagle_swarm_core.agent:main",
            "coordinator=eagle_swarm_core.coordinator:main",
            "target_detector=eagle_swarm_core.target_detector:main",
            "mission_demo=eagle_swarm_core.mission_demo:main",
            "role_manager=eagle_swarm_core.role_manager:main",
            "go_to_target_server=eagle_swarm_core.go_to_target_server:main",
        ]
    },
)
