FROM python:3.6-alpine

RUN apk --no-cache add git

# add a non-root user and give them ownership
RUN adduser -D -u 9000 app && \
    # repo
    mkdir /repo && \
    chown -R app:app /repo && \
    # app code
    mkdir /usr/src/app && \
    chown -R app:app /usr/src/app

# add the pullrequest utility to easily create pull requests on different git hosts
WORKDIR /usr/src/app
ENV PULLREQUEST_VERSION=2.0.0-alpha.11
ADD https://github.com/dependencies-io/pullrequest/releases/download/${PULLREQUEST_VERSION}/pullrequest_${PULLREQUEST_VERSION}_linux_amd64.tar.gz .
RUN mkdir pullrequest && \
    tar -zxvf pullrequest_${PULLREQUEST_VERSION}_linux_amd64.tar.gz -C pullrequest && \
    ln -s /usr/src/app/pullrequest/pullrequest /usr/local/bin/pullrequest

# add pipenv reference PipFile implementation
RUN easy_install pip \
    && pip install --upgrade pipenv \
    && pip install pipenv

# run everything from here on as non-root
USER app

RUN git config --global user.email "bot@dependencies.io"
RUN git config --global user.name "Dependencies.io Bot"

ADD src/ /usr/src/app/

WORKDIR /repo

ENTRYPOINT ["python", "/usr/src/app/entrypoint.py"]
