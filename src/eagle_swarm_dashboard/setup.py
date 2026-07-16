from setuptools import find_packages, setup

package_name = 'eagle_swarm_dashboard'

setup(
    name=package_name,
    version='1.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Haya Medhat Abdelhamid',
    maintainer_email='haya@example.com',
    description='Terminal and browser-based Digital Twin dashboards for EAGLE SWARM',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'dashboard=eagle_swarm_dashboard.dashboard:main',
            'digital_twin=eagle_swarm_dashboard.web_dashboard:main',
        ],
    },
)
