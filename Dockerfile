# set base image (host OS)
FROM python:3.8

# set the working directory in the container
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# copy the dependencies file to the working directory
COPY requirements.txt /usr/src/app/

# install dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /usr/src/app/requirements.txt

# copy the content of the local src directory to the working directory
COPY ./app /usr/src/app

# Create empty dir for log and database files
RUN mkdir -p /usr/src/app/log
RUN mkdir -p /usr/src/app/db

# command to run on container start
CMD [ "python", "./startbot.py" ]
