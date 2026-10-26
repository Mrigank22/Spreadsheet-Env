# LibreOffice Calc (headless) used only to cross-check the formula engine.
FROM debian:trixie-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends libreoffice-calc-nogui \
 && rm -rf /var/lib/apt/lists/*
# Profile that forces a full recalculation of every .xlsx on load and enables
# iterative calculation (for models with intended circularity).
COPY lo_profile /lo_profile
WORKDIR /data
