#!/usr/bin/env bash

export GOPATH=$WORKSPACE

go get golang.org/x/crypto/ssh
go install golang.org/x/crypto/ssh
go get golang.org/x/tools/cmd/goimports
go install golang.org/x/tools/cmd/goimports

export PATH=$PATH:$WORKSPACE/bin

#go vet ./...
 
/bin/bash $WORKSPACE/golang/scripts/format
