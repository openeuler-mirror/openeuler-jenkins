#!/usr/bin/env bash

export GOPATH=$WORKSPACE/$BUILD_ID

go get golang.org/x/crypto/ssh
go install golang.org/x/crypto/ssh
go get golang.org/x/tools/cmd/goimports
go install golang.org/x/tools/cmd/goimports

export PATH=$PATH:$WORKSPACE/$BUILD_ID/bin

#go vet ./...
 
/bin/bash $WORKSPACE/$BUILD_ID/openeuler-jenkins/golang/scripts/format

