#!/bin/bash

mkdir -p test
cd test

if [ ! -d "cal.com" ]; then
    echo "Cloning cal.com..."
    git clone https://github.com/calcom/cal.com
else
    echo "cal.com already exists, skipping..."
fi

if [ ! -d "formbricks" ]; then
    echo "Cloning formbricks..."
    git clone https://github.com/formbricks/formbricks
else
    echo "formbricks already exists, skipping..."
fi

if [ ! -d "dub" ]; then
    echo "Cloning dubinc/dub"
    git clone https://github.com/dubinc/dub
else
    echo "dub already exists, skipping..."
fi

if [ ! -d "twenty" ]; then
    echo "Cloning twentyhq/twenty"
    git clone https://github.com/twentyhq/twenty
else
    echo "twenty already exists, skipping..."
fi

if [ ! -d "rallly" ]; then
    echo "Cloning lukevella/rallly"
    git clone https://github.com/lukevella/rallly
else
    echo "rallly already exists, skipping..."
fi

if [ ! -d "plane" ]; then
    echo "Cloning makeplane/plane"
    git clone https://github.com/makeplane/plane
else
    echo "plane already exists, skipping..."
fi

echo "All repositories cloned successfully!"
