FROM python:3.8
ADD . /srv/reserv/
RUN pip3 install -r /srv/reserv/requirements.txt
ENTRYPOINT ["python3", "/srv/reserv/src/reserv.py", "-c", "/srv/reserv/config.json", "-f", "/src/reserv/files/"]