# build image manifest for multi arch
# usage:
#  sh manifest.sh {name} {version}
#  example: sh manifest.sh jenkins/obs 20200601

name=$1         # 镜像名
version=$2      # 镜像版本

image=swr.cn-north-4.myhuaweicloud.com/openeuler/${name}:${version}
image_x86_64=swr.cn-north-4.myhuaweicloud.com/openeuler/x86-64/${name}:${version}
image_aarch64=swr.cn-north-4.myhuaweicloud.com/openeuler/aarch64/${name}:${version}

echo "create manifest"
docker manifest create -a ${image} ${image_x86_64} ${image_aarch64}

echo "annotate manifest of arch amd64"
docker manifest annotate ${image} ${image_x86_64} --os linux --arch amd64

echo "annotate manifest of arch aarch64"
docker manifest annotate ${image} ${image_aarch64} --os linux --arch arm64/v8

echo "push manifest"
docker manifest push --purge ${image}

echo "build image manifest for multi arch ... pass"
