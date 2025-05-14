# archival-packaging-tool (APT)

A tool for creating a Bagit zip file.

## Development

- To preview a list of available Makefile commands: `make help`
- To install with dev dependencies: `make install`
- To update dependencies: `make update`
- To run unit tests: `make test`
- To lint the repo: `make lint`

## Testing Locally with AWS SAM

### SAM Installation

Ensure that AWS SAM CLI is installed: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html.

All following actions and commands should be performed from the root of the project (i.e. same directory as the `Dockerfile`).

### Building and Configuration

1- Create a JSON file for SAM that has environment variables for the container 

- copy `tests/sam/env.json.template` to `tests/sam/env.json` (which is git ignored)
- fill in missing sensitive env vars

**NOTE:** AWS credentials are automatically passed from the terminal context that runs `make sam-run`; they do not need to be explicitly set as env vars.

2- Build Docker image:
```shell
make sam-build
```

### Invoking Lambda via HTTP requests

The following outlines how to run the Lambda SAM docker image as an HTTP endpoint, accepting requests and returning respnoses similar to a lambda behind an ALB, Function URL, or API Gateway.

1- Ensure AWS Dev `AWSAdministratorAccess` (_TODO: update once an AWS SSO role is created for this project_) credentials set in terminal and any other env vars in `tests/sam/env.json` up-to-date.
 
2- Run HTTP server:
```shell
make sam-http-run
```

This starts a server at `http://localhost:3000`.  Requests must include a path, e.g. `/apt`, but are arbitrary insofar as the lambda does not utilize them in the request payload. 

3- In another terminal, perform an HTTP request via another `Makefile` command:
```shell
make sam-http-ping
```

Response should have an HTTP status of `200` and respond with:
```json
{
    "response": "pong"
}
```

### Invoking Lambda directly

While Lambdas can be invoked via HTTP methods (ALB, Function URL, etc.), they are also often invoked directly with an `event` payload.  To do so with SAM, you do **not** need to first start an HTTP server with `make sam-run`, you can invoke the function image directly:

```shell
echo '{"action": "ping","challenge_secret":"totally-local-archival-packaging"}' | sam local invoke -e -
```

Response:
```text
{"statusCode": 200, "statusDescription": "200 OK", "headers": {"Content-Type": "application/json"}, "isBase64Encoded": false, "body": "{\"response\": \"pong\"}"}
```

As you can see from this response, the lambda is still returning a dictionary that _would_ work for an HTTP response, but is actually just a dictionary with the required information.

It's unknown at this time if APT will get invoked via non-HTTP methods, but SAM will be helpful for testing and development if so.


## Environment Variables

### Required

```shell
SENTRY_DSN=### If set to a valid Sentry DSN, enables Sentry exception monitoring. This is not needed for local development.
WORKSPACE=### Set to `dev` for local development, this will be set to `stage` and `prod` in those environments by Terraform.
CHALLENGE_SECRET=### Secret string that is passed as part of lambda invocation payload and checked before running
```

### Optional

```shell
WARNING_ONLY_LOGGERS=### comma separated list of libraries to limit to WARNING logging level
WORKSPACE_ROOT_DIR=### Root directory where Bagit zip files will be temporarily created, then cleaned up; for deployed Lambda this will be the EFS mount.  Defaults to /tmp.
```