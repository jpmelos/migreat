FROM python:3.7
ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=on \
  PIP_DISABLE_PIP_VERSION_CHECK=on

WORKDIR /
RUN python -m venv venv
ENV VIRTUAL_ENV=/venv
ENV PATH=$VIRTUAL_ENV/bin:$PATH
RUN pip install -U setuptools pip wheel

WORKDIR /code

ADD min-requirements.txt .
ADD dev-min-requirements.txt .

RUN pip install -r min-requirements.txt
RUN pip install -r dev-min-requirements.txt

ENTRYPOINT ["pytest"]

COPY . .
