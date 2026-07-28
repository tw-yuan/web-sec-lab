FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask

COPY app/ /app/

# Flag lives outside the files directory — students must traverse to reach it
ENV FLAG=AIS3{p4th_tr4v3rs4l_3sc4p3d_th3_s4ndb0x}
RUN echo "${FLAG}" > /flag.txt && chmod 644 /flag.txt

EXPOSE 5000

CMD ["python", "app.py"]
