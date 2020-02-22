FROM python:3.8-alpine
COPY requirements.txt /root
RUN pip install -r /root/requirements.txt
COPY dar.py /root/
CMD python /root/dar.py
