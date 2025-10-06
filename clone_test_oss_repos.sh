#!/bin/bash

mkdir -p test
cd test

echo "Cloning umami..."
git clone https://github.com/umami-software/umami

echo "Cloning cal.com..."
git clone https://github.com/calcom/cal.com

echo "Cloning formbricks..."
git clone https://github.com/formbricks/formbricks

echo "All repositories cloned successfully!"
