FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app \
    DENO_INSTALL=/usr/local
WORKDIR /app

# ffmpeg (Debian build includes libass for burned-in ASS subtitles),
# system fonts the worker's font fallback list expects, fontconfig.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg fontconfig \
        fonts-dejavu-core fonts-liberation fonts-noto-core fonts-freefont-ttf \
        curl ca-certificates unzip libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Deno: yt-dlp needs a JavaScript runtime for YouTube extraction.
RUN curl -fsSL -o /tmp/deno.zip \
        https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
    && unzip -o /tmp/deno.zip -d /usr/local/bin && rm /tmp/deno.zip && deno --version

# CPU-only torch first, then the rest
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# OpenCV DNN face detector (paths hard-coded in worker.py: /app/models/...)
RUN mkdir -p /app/models \
 && curl -fsSL -o /app/models/deploy.prototxt \
      https://raw.githubusercontent.com/opencv/opencv/4.x/samples/dnn/face_detector/deploy.prototxt \
 && curl -fsSL -o /app/models/res10_300x300_ssd_iter_140000.caffemodel \
      https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel

# Display fonts for captions go in fonts/ (rebuild task R-19); copied if present.
COPY fonts/ /usr/share/fonts/truetype/clipflow/
RUN fc-cache -f

COPY --from=shared . /app/shared
COPY assets/ /app/assets/
COPY worker.py /app/worker.py

CMD ["python", "-u", "/app/worker.py"]
