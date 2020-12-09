# set base image (host OS)
FROM python:3.8

# set the working directory in the container
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

# copy the dependencies file to the working directory
COPY requirements.txt /usr/src/app/

# install dependencies
RUN pip install --upgrade pip
RUN apt-get update
# Uncomment if build fail on cv2 dependencies:
# RUN apt-get install ffmpeg libsm6 libxext6  -y
RUN pip install --no-cache-dir -r /usr/src/app/requirements.txt

# copy the content of the local src directory to the working directory
COPY ./app /usr/src/app

# command to run on container start
CMD [ "python", "./startbot.py" ]
