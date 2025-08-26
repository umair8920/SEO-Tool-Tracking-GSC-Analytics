# Use an official Python 3.12.8 runtime as a parent image
FROM python:3.12.8-slim

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy necessary directories first for better caching
COPY static/ /app/static/
COPY templates/ /app/templates/

# Copy the rest of the application
COPY . .

# Ensure static files are accessible
ENV STATIC_ROOT=/app/static

# Expose the port FastAPI will run on (Cloud Run default: 8080)
EXPOSE 8080

# Command to run the app using Uvicorn with proxy headers enabled
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
