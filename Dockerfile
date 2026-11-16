# Ghim theo digest để build lặp lại được (mage-ai 0.9.79, Python 3.10).
FROM mageai/mageai:latest@sha256:440970d14b6e1c66e879650c35564cf5125cbbed56032c0fb8337808fdf012fe

# Gói thêm cho môi trường Python của Mage (chỉ những gì Mage chưa có).
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# dbt cài trong virtualenv riêng: dbt-core mới cần click>=8.3 và protobuf>=6,
# xung đột với click 8.1 / typer 0.9 / protobuf 4 mà CLI của Mage dùng.
# Chỉ symlink lệnh `dbt`, không đưa venv vào PATH để `python` vẫn là của Mage.
COPY requirements-dbt.txt /tmp/requirements-dbt.txt
RUN python3 -m venv /opt/dbt \
 && /opt/dbt/bin/pip install --no-cache-dir -r /tmp/requirements-dbt.txt \
 && ln -sf /opt/dbt/bin/dbt /usr/local/bin/dbt
