# docker images
## openeuler
- swr.cn-north-4.myhuaweicloud.com/openeuler/openeuler:21.03
- swr.cn-north-4.myhuaweicloud.com/openeuler/openeuler:20.09
- swr.cn-north-4.myhuaweicloud.com/openeuler/openeuler:20.03-lts-sp1
- swr.cn-north-4.myhuaweicloud.com/openeuler/openeuler:20.03-lts

## openjdk 11-jdk-stretch based on openeuler
- swr.cn-north-4.myhuaweicloud.com/openeuler/openjdk/11-jdk-stretch:21.03
- swr.cn-north-4.myhuaweicloud.com/openeuler/openjdk/11-jdk-stretch:20.09
- swr.cn-north-4.myhuaweicloud.com/openeuler/openjdk/11-jdk-stretch:20.03-lts-sp1
- swr.cn-north-4.myhuaweicloud.com/openeuler/openjdk/11-jdk-stretch:20.03-lts

> Dockerfile: openjdk-openeuler

## openeuler ci image based on openjdk
- swr.cn-north-4.myhuaweicloud.com/openeuler/ci/common:21.03
- swr.cn-north-4.myhuaweicloud.com/openeuler/ci/common:20.09
- swr.cn-north-4.myhuaweicloud.com/openeuler/ci/common:20.03-lts-sp1
- swr.cn-north-4.myhuaweicloud.com/openeuler/ci/common:20.03-lts

> Dockerfile: ci-common

## src-openeuler ci image based on openjdk
- swr.cn-north-4.myhuaweicloud.com/openeuler/ci/soe:base

> Dockerfile: ci-soe-base

> choose an openjdk image that from stable openeuler version

- swr.cn-north-4.myhuaweicloud.com/openeuler/ci/soe:{version}
