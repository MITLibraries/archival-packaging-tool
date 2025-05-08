FROM public.ecr.aws/lambda/python:3.12

# Copy function code
COPY . ${LAMBDA_TASK_ROOT}/

# Install dependencies
RUN pip3 install pipenv
RUN pipenv requirements > requirements.txt
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Create an empty .env file to appease the Makefile "include .env" in CI
RUN touch .env

CMD [ "apt.lambda_handler.lambda_handler" ]