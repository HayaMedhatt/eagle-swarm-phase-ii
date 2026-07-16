from setuptools import find_packages, setup

package_name = 'eagle_swarm_common'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Haya Medhat Abdelhamid',
    maintainer_email='haya@example.com',
    description='ROS-independent EAGLE SWARM decision policies.',
    license='Apache-2.0',
)
