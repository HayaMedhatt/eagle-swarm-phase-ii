from glob import glob

from setuptools import find_packages, setup

package_name = "eagle_swarm_sim"

setup(
    name=package_name,
    version="1.0.0",
    packages=find_packages(),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/worlds", glob("worlds/*.sdf")),
        (
            "share/" + package_name + "/models/confirmed_target",
            glob("models/confirmed_target/*"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Haya Medhat Abdelhamid",
    maintainer_email="haya@example.com",
    description="Gazebo assets and independent separation safety layer.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "safety_monitor=eagle_swarm_sim.safety_monitor:main",
        ]
    },
)
