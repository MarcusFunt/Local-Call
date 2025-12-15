
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y git build-essential

RUN git clone https://github.com/ggerganov/whisper.cpp.git /app/whisper.cpp

WORKDIR /app/whisper.cpp

RUN make

CMD ["./server", "-m", "models/ggml-base.en.bin", "--host", "0.0.0.0", "--port", "8080"]
