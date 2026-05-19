# Kubernetes Cluster-based Packaging Solution

## Single package build task

### Design logic

- Deploy the Kubernetes cluster in the x86-64 and AArch64 architectures.
- Configure the cluster as **Jenkins slave**.
- **Jenkins master** runs in the Kubernetes cluster in the x86-64 architecture.

### Pipeline job

> Only one instance is running for the same task.

#### trigger

- GitCode triggering
- The gating task is executed at the same time. The CPU architecture is not limited. If the task fails, the task is stopped and a comment is added to the PR.
- Parameters are successfully transferred to the downstream **job**.
  - Project name (**repo**)
  - Branch (**branch**)
  - Id of the Pull Request (**prid**)
  - Initiator (**committer**)

#### multiarch

- The x86_64 and AArch64 architectures are supported.
- Triggered after the trigger task is successful.
- Run the osc_build_k8s.py on GitCode for building.

#### comment

- Collect the gating and build results.
- Call the API [**Submit a comment on the pull request**] to send the result to GitCode.
- The CPU architecture is not limited.

## Creating a Jenkins/obs image

### Mechanism

- The docker service is deployed in the Kubernetes cluster. The internal service address provided for external systems is tcp://docker.jenkins:2376.
- Install the docker plugin on Jenkins and connect it to the docker service in the Kubernetes cluster.
- Configure the image creation pipeline task obs-image in Jenkins.
- Triggering mode: After the tag is added to the code repository ci_check, the task is manually triggered. The build with parameterrs plugin must be installed on Jenkins.

### Pipeline task obs-image

> The Kubernetes agent that runs the task must have the docker client.

#### Task: _trigger

- (Optional) Check the Dockerfile.
- Set parameters.
  - **name** [jenkins/obs]
  - **version** [obtained from the tag]

#### Task: build-image-aarch64 & build-image-x86-64

- Select **Build/Publish Docker Image** in the build process.
- Configure the **Registry Credentials** for pushing images.

#### Task: manifest

Multi-arch support
> Register credentials during docker manifest push?

## Contents

| Directory| Description|
| --- | --- |
|ac/framework | Gating framework|
|ac/acl | Gating tasks. Each gating item corresponds to a directory.|
|ac/common | Gating common code|
|build| Single-package build|
|jobs| Jenkins task management|
|conf|Configuration|
|proxy|Third-party API agent|
|utils|Common code, logs, and more.|
