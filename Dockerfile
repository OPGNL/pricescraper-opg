FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Playwright browser dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    # Playwright dependencies
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libgtk-3-0 \
    libatspi2.0-0 \
    libxrandr2 \
    libasound2 \
    libxss1 \
    xvfb \
    # Fonts
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-thai-tlwg \
    fonts-freefont-ttf \
    fonts-unifont \
    fonts-liberation \
    && wget -q -O /tmp/google-chrome-key.pub https://dl-ssl.google.com/linux/linux_signing_key.pub \
    && gpg --dearmor < /tmp/google-chrome-key.pub > /etc/apt/keyrings/google-chrome.gpg \
    && sh -c 'echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/google-chrome-key.pub

# Set environment to production
ENV ENV=production

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its browsers
RUN playwright install chromium

# Copy the rest of the application
COPY . .

# Copy and setup startup script
COPY start.sh /app/start.sh
RUN chmod 755 /app/start.sh

# Expose the port
EXPOSE 8000

# Start the application with the startup script
CMD ["/app/start.sh"]
