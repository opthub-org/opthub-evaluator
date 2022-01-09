TAG ?= opthub-evaluator
DOCKER ?= /var/run/docker.sock

all: image start

start: image
	docker run --rm -v $(DOCKER):$(DOCKER) $(TAG)

image:
	docker build -t $(TAG) .

install:
	pip install -e .
