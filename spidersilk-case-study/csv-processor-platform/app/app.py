import os
import csv
import io
import boto3
from flask import Flask, request, render_template_string, redirect, url_for

app = Flask(__name__)

# Fetch configurations from environment variables injected by Helm
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize boto3 S3 client 
# When running on EKS/kops with IAM Roles for Service Accounts (IRSA), credentials are automatically picked up
s3_client = boto3.client('s3', region_name=AWS_REGION)

HTML_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CSV Processing Hub</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 40px; background: #f4f6f9; color: #333; }
        .container { max-width: 1000px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1, h2 { color: #0f4c81; margin-top: 0; }
        .upload-section { background: #eef5fc; border: 2px dashed #0f4c81; border-radius: 6px; padding: 30px; text-align: center; margin-bottom: 30px; }
        .file-input { margin: 15px 0; }
        .btn { background: #0f4c81; color: white; border: none; padding: 12px 24px; border-radius: 4px; font-size: 14px; cursor: pointer; font-weight: bold; }
        .btn:hover { background: #145d9c; }
        .alert { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; padding: 15px; border-radius: 4px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e0e0e0; }
        th { background: #0f4c81; color: white; }
        tr:nth-child(even) { background: #f9f9f9; }
        .file-list { list-style: none; padding: 0; }
        .file-list li { background: #f8f9fa; padding: 12px 15px; margin-bottom: 8px; border-left: 4px solid #0f4c81; border-radius: 0 4px 4px 0; display: flex; justify-content: space-between; align-items: center; }
        .meta-info { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        {% if msg %}
            <div class="alert">{{ msg }}</div>
        {% endif %}
        
        <h1>CSV Asset Management Portal</h1>
        
        <div class="upload-section">
            <h2>Upload Inventory Dataset</h2>
            <form action="/upload" method="POST" enctype="multipart/form-data">
                <input type="file" name="csv_file" accept=".csv" class="file-input" required><br>
                <button type="submit" class="btn">Parse, Process & Sync to S3</button>
            </form>
        </div>

        {% if rows %}
            <h2>Parsed Elements (Current View: {{ current_file }})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Line #</th>
                        <th>Item ID / SKU</th>
                        <th>Product Description</th>
                        <th>Price</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in rows %}
                        <tr>
                            <td>{{ loop.index }}</td>
                            <td>{{ row[0] if row|length > 0 else '' }}</td>
                            <td>{{ row[1] if row|length > 1 else '' }}</td>
                            <td>{{ row[2] if row|length > 2 else '' }}</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
            <br><hr><br>
        {% endif %}

        <h2>Previously Processed Files (S3 Active Storage)</h2>
        <ul class="file-list">
            {% for file in files %}
                <li>
                    <span>📄 <strong>{{ file.Key }}</strong></span>
                    <span class="meta-info">Last Modified: {{ file.LastModified.strftime('%Y-%m-%d %H:%M:%S UTC') }}</span>
                </li>
            {% else %}
                <li>No records found in S3 bucket "{{ bucket_name }}".</li>
            {% endfor %}
        </ul>
    </div>
</body>
</html>
"""

def get_s3_file_list():
    if not S3_BUCKET:
        return []
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        return response.get('Contents', [])
    except Exception as e:
        print(f"Error querying S3 list: {str(e)}")
        return []

@app.route('/', methods=['GET'])
def index():
    files = get_s3_file_list()
    return render_template_string(HTML_LAYOUT, files=files, bucket_name=S3_BUCKET)

@app.route('/upload', methods=['POST'])
def upload():
    if 'csv_file' not in request.files:
        return redirect(url_for('index'))
    
    file = request.files['csv_file']
    if file.filename == '':
        return redirect(url_for('index'))
    
    if file and file.filename.endswith('.csv'):
        filename = file.filename
        raw_bytes = file.read()
        
        # 1. Save file directly to S3 Bucket
        s3_error = None
        if S3_BUCKET:
            try:
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=filename,
                    Body=raw_bytes,
                    ContentType='text/csv'
                )
            except Exception as e:
                s3_error = str(e)
        else:
            s3_error = "S3_BUCKET_NAME environment variable not configured."

        # 2. Read and parse line contents to display back to browser
        decoded_content = raw_bytes.decode('utf-8')
        csv_file_obj = io.StringIO(decoded_content)
        reader = csv.reader(csv_file_obj)
        rows = [row for row in reader if row] # filter out empty array hooks
        
        files = get_s3_file_list()
        msg = f"Successfully processed '{filename}' and synchronized with S3 bucket." if not s3_error else f"Processed locally but failed to store on S3: {s3_error}"
        
        return render_template_string(HTML_LAYOUT, msg=msg, rows=rows, current_file=filename, files=files, bucket_name=S3_BUCKET)
        
    return "Invalid file format. Please upload a structured .csv document.", 400

if __name__ == '__main__':
    # Internal multi-container networking relies on mapping to port 8080
    app.run(host='0.0.0.0', port=8080)
