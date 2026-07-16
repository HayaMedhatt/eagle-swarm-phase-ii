from setuptools import find_packages, setup

package_name = "eagle_swarm_tools"

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
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Haya Medhat Abdelhamid",
    maintainer_email="haya@example.com",
    description="Fault injection and demo utilities.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "inject_fault=eagle_swarm_tools.inject_fault:main",
            "run_scenario=eagle_swarm_tools.scenario_runner:main",
            "summarize_evidence=eagle_swarm_tools.evidence_report:main",
        ]
    },
)
