#!/usr/bin/env bash

go get golang.org/x/crypto/ssh
go get golang.org/x/tools/cmd/goimports

#go vet ./...
 
/bin/bash $WORKSPACE/golang/scripts/format
