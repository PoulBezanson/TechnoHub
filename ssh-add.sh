#!/bin/bash

[ -n "$SSH_AUTH_SOCK" ] || eval $(ssh-agent)
ssh-add ~/.ssh/hite

# about problem
# https://superuser.com/questions/1535186/why-are-ssh-agent-and-ssh-add-not-working-together-in-one-bash-script
