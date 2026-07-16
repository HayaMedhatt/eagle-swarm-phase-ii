from glob import glob
from setuptools import find_packages, setup

package_name = 'eagle_swarm_px4'
setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Haya Medhat Abdelhamid',
    maintainer_email='haya@example.com',
    description='PX4 SITL/MAVROS adapter boundary for EAGLE SWARM',
    license='Apache-2.0',
    entry_points={'console_scripts': ['px4_adapter=eagle_swarm_px4.px4_adapter:main']},
)
