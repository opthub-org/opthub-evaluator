# OptHub Evaluator
OptHub Evaluator is a worker program that evaluates a solution submitted to OptHub.

## Requirements
- Python >=3.6
- Docker >=1.12

See also [requirements.txt](requirements.txt) for dependent python packages.

## Installation
```
$ pip install opthub-evaluator
```

## Usage
### How to start an evaluator
Login the docker registry where the problem image is stored.
```
$ docker login <registry>
```

Start an evaluator.
```
$ opthub-evaluator
```

Options
|Parameter|Type|Default|Description|
|-|-|-|-|
|url|path|https://opthub-api.herokuapp.com/v1/graphql|URL to OptHub|
|apikey|str||ApiKey|
|interval|int|2|Polling interval|
|verify/no-verify|bool|True|Verify SSL certificate|
|retries|int|3|Retries to establish HTTPS connection|
|timeout|int|600|Timeout to process a query|
|rm|||Remove containers after exit|
|quiet|||Be quieter|
|verbose|||Be more verbose|
|config|path|opthub-evaluator.yml|Configuration file|

### How to make an problem image
1. Write a problem program in your favorite language.
2. Dockerize it.
3. Push the docker image to DockerHub or somewhere else accessible from OptHub.
   For this purpose, OptHub hosts its own docker private registry.
4. Register the image tag to OptHub.

See also [example](example/).

## Author
Naoki Hamada (hmkz@s101.xrea.com)

## License
MIT
