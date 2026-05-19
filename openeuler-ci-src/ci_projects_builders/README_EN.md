# Configuring openEuler Code Repository Gating

openEuler contains all artifact repositories (repositories starting with src-openeuler) and code repositories (repositories starting with openeuler). Currently, all artifact repositories are configured with the pull request (PR) gating while code repositories are not configured with the PR gating by default. This document describes how to configure the PR gating for openEuler code repositories.

## Account Authorization

The gating of all openEuler artifact repositories and code repositories is hosted on Jenkins. To access the Jenkins project, you need to be authorized through Authing. Click **`Sign in with authing`** and select GitCode authorization. If your bounded GitCodeemail address has been registered on Authing and added to the openeuler-jenkins group (the bounded GitCode email address is used to submit a PR to openeuler-jenkins on GitCode for authing configuration), you can access the Jenkins project after authorization.
If you want to view or modify the configuration of the corresponding project, you also need a Jenkins account. For details about how to register an account and configure project permissions, contact the author.

## Submitting a PR

Now, you can submit a PR to automatically create the gating for openEuler code repositories on Jenkins. The repository to which the PR is submitted is openeuler-jenkins on GitCode, and the path in the repository is **openeuler-ci/{repo}.yaml**. That is, you need to create a YAML file with the same name as the repository in the **openeuler-ci** directory. The following uses **openeuler/website** as an example. The content is as follows:

```sh
repo_name: website
container_level: l1
init_shell: "echo hello\necho $?"
users:
  - login_name: *xxx*
    name: *xyz*
    email: *xxx*@*yyy*.com
    gitee_id: *xxx*
```

In the configuration file, **repo_name** indicates the name of the repository to be configured, **container_level** indicates the portfolio level of the container memory and disk. **l1** indicates 2 cores and 4 GB to 4 cores and 8 GB, and **l2** indicates 4 cores and 6 GB or higher. **init_shell** is an array of x86-64 and AArch64. The **users** project is an array, and each item in the array is the configuration of a user. **login_name** is the Jenkins login account, **name** is the name of the account on Jenkins, and **email** is the email address bound to GitCode for Authing authorization.
After the PR is merged, the GitCode Webhook triggers the automatic creation of a project corresponding to the openEuler code repository on Jenkins.

## Gating Process

The PR gating of a code repository requires that a project with the corresponding repository name be available in each of the four directories for triggering, building, and commenting: **multiarch/openeuler/trigger/**, **multiarch/openeuler/x86/**, **multiarch/openeuler/aarch64/**, and **multiarch/openeuler/comment/**. The preceding PR merging process enables the four projects to be created.

After a project of the openEuler code repository is created and configured on Jenkins, a PR submission to the openEuler code repository or a `/retest` comment in the existing PR will trigger the project with the same name as the repository under **`multiarch/openeuler/trigger/`**. When the project under **`multiarch/openeuler/trigger/`** finishes running, projects with the same name under **`multiarch/openeuler/x86/`** and **`multiarch/openeuler/aarch64/`** (or more architectures) will be triggered. When the two or more projects under **`multiarch/openeuler/x86/`** and **`multiarch/openeuler/aarch64/`** (or more architectures) finish running, the project with the same name under **`multiarch/openeuler/comment/`** will be triggered. Finally, the comment project will call GitCode's comment API to post the gating results to the PR.

To customize the gating, you only need to customize the shell in the project configuration of different architectures, such as `multiarch/openeuler/x86/` and `multiarch/openeuler/aarch64/`. However, you are advised not to use commands such as **chroot** in the shell.

## Supporting for Other Architectures

The preceding content is universal for the configuration of most projects. If you need more customization, such as running the project in containers on other architectures, you can contact the author and provide the corresponding Docker image or Dockerfile.
