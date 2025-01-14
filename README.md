import pyodbc
import pandas as pd
from flask import Flask, jsonify, request

app = Flask(__name__)

# Database connection strings
DB1_CONNECTION_STRING = (
    "Driver={SQL Server};"
    "Server=server1;"
    "Database=database1;"
    "UID=username;"
    "PWD=password;"
)

DB2_CONNECTION_STRING = (
    "Driver={SQL Server};"
    "Server=server2;"
    "Database=database2;"
    "UID=username;"
    "PWD=password;"
)

# Endpoint to fetch data for DataTable with server-side processing
@app.route('/fetch-t1', methods=['POST'])
def fetch_t1():
    request_data = request.json
    draw = int(request_data.get('draw', 1))
    start = int(request_data.get('start', 0))
    length = int(request_data.get('length', 10))
    order_column = int(request_data.get('order[0][column]', 0))
    order_dir = request_data.get('order[0][dir]', 'asc')
    search_value = request_data.get('search[value]', '').strip()

    columns = ['f1', 'f2', 'f3', 'f4', 'f5']
    order_column_name = columns[order_column] if order_column < len(columns) else 'f1'

    try:
        conn1 = pyodbc.connect(DB1_CONNECTION_STRING)
        cursor1 = conn1.cursor()

        # Base query
        query = f"""
            SELECT *,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM database2.dbo.t2 WHERE t2.f1 = t1.f1
                   ) THEN 1 ELSE 0 END AS f1_exists,
                   CASE WHEN EXISTS (
                       SELECT 1 FROM database2.dbo.t2 WHERE t2.f2 = t1.f2
                   ) THEN 1 ELSE 0 END AS f2_exists
            FROM t1
            WHERE f3 != 'miscellaneous' AND f5 = 'test_value'
        """

        if search_value:
            query += f" AND (f1 LIKE ? OR f2 LIKE ? OR f3 LIKE ? OR f4 LIKE ? OR f5 LIKE ?)"
            search_params = [f"%{search_value}%"] * 5
        else:
            search_params = []

        query += f" ORDER BY {order_column_name} {order_dir}"
        paginated_query = f"""
            SELECT * FROM ({query}) AS subquery
            ORDER BY {order_column_name} {order_dir}
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """

        # Total records
        cursor1.execute(f"SELECT COUNT(*) FROM t1 WHERE f3 != 'miscellaneous' AND f5 = 'test_value'")
        total_records = cursor1.fetchone()[0]

        # Filtered records
        if search_value:
            cursor1.execute(f"SELECT COUNT(*) FROM ({query}) AS subquery", *search_params)
            total_filtered_records = cursor1.fetchone()[0]
        else:
            total_filtered_records = total_records

        # Fetch data
        cursor1.execute(paginated_query, *search_params, start, length)
        rows = cursor1.fetchall()
        column_names = [desc[0] for desc in cursor1.description]
        data = [dict(zip(column_names, row)) for row in rows]

        conn1.close()

        return jsonify({
            'draw': draw,
            'recordsTotal': total_records,
            'recordsFiltered': total_filtered_records,
            'data': data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Endpoint to add records to t2
@app.route('/add-to-t2', methods=['POST'])
def add_to_t2():
    records = request.json
    if not records:
        return jsonify({"error": "No records provided."}), 400

    try:
        conn2 = pyodbc.connect(DB2_CONNECTION_STRING)
        cursor2 = conn2.cursor()

        duplicates_f1 = set()
        duplicates_f2 = set()

        for record in records:
            if "f1" in record:
                cursor2.execute("SELECT COUNT(*) FROM t2 WHERE f1 = ?", record['f1'])
                if cursor2.fetchone()[0] > 0:
                    duplicates_f1.add(record['f1'])

            if "f2" in record:
                cursor2.execute("SELECT COUNT(*) FROM t2 WHERE f2 = ?", record['f2'])
                if cursor2.fetchone()[0] > 0:
                    duplicates_f2.add(record['f2'])

            if not (record.get('f1') in duplicates_f1 or record.get('f2') in duplicates_f2):
                cursor2.execute("INSERT INTO t2 (f1, f2) VALUES (?, ?)", (record.get('f1'), record.get('f2')))

        conn2.commit()
        conn2.close()

        if duplicates_f1 or duplicates_f2:
            return jsonify({
                "error": "Some values already exist in t2.",
                "duplicates": {
                    "f1": list(duplicates_f1),
                    "f2": list(duplicates_f2)
                }
            }), 400

        return jsonify({"message": "Successfully added to t2."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)






<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataTable with Server-Side Processing</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.5/css/jquery.dataTables.min.css">
</head>
<body>
    <table id="t1-table" class="display" style="width:100%">
        <thead>
            <tr>
                <th>f1</th>
                <th>f2</th>
                <th>f3</th>
                <th>f4</th>
                <th>f5</th>
                <th>Select f1</th>
                <th>Select f2</th>
            </tr>
        </thead>
    </table>
    <button id="add-to-t2">Add Selected to t2</button>
    <div id="error-message" style="color: red;"></div>

    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.5/js/jquery.dataTables.min.js"></script>
    <script>
        $(document).ready(function () {
            const table = $('#t1-table').DataTable({
                serverSide: true,
                processing: true,
                ajax: {
                    url: '/fetch-t1',
                    type: 'POST',
                    contentType: 'application/json',
                    data: function (d) {
                        return JSON.stringify(d);
                    }
                },
                columns: [
                    { data: 'f1' },
                    { data: 'f2' },
                    { data: 'f3' },
                    { data: 'f4' },
                    { data: 'f5' },
                    {
                        data: 'f1',
                        render: function (data, type, row) {
                            return `<input type="checkbox" class="select-f1" value="${data}" ${row.f1_exists ? 'disabled' : ''}>`;
                        }
                    },
                    {
                        data: 'f2',
                        render: function (data, type, row) {
                            return `<input type="checkbox" class="select-f2" value="${data}" ${row.f2_exists ? 'disabled' : ''}>`;
                        }
                    }
                ],
                order: [[0, 'asc']]
            });

            $('#t1-table').on('change', '.select-f1, .select-f2', function () {
                const value = $(this).val();
                const isChecked = $(this).is(':checked');

                if (isChecked) {
                    $(`.select-f1[value="${value}"], .select-f2[value="${value}"]`).prop('disabled', true);
                } else {
                    $(`.select-f1[value="${value}"], .select-f2[value="${value}"]`).prop('disabled', false);
                }
            });

            $('#add-to-t2').click(function () {
                const payload = [];
                $('.select-f1:checked').each(function () {
                    payload.push({ f1: $(this).val() });
                });
                $('.select-f2:checked').each(function () {
                    payload.push({ f2: $(this).val() });
                });

                if (payload.length === 0) {
                    alert('No records selected.');
                    return;
                }

                $.ajax({
                    url: '/add-to-t2',
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(payload),
                    success: function (response) {
                        alert(response.message);
                        table.ajax.reload();
                    },
                    error: function (xhr) {
                        const errorData = xhr.responseJSON;
                        if (errorData.duplicates) {
                            $('#error-message').html(`
                                Duplicates found: <br>
                                f1: ${errorData.duplicates.f1.join(', ')}<br>
                                f2: ${errorData.duplicates.f2.join(', ')}
                            `);
                        } else {
                            $('#error-message').text(errorData.error);
                        }
                    }
                });
            });
        });
    </script>
</body>
</html>









popup



<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>File Path Selector with Popup</title>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        /* Modal styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.4);
            justify-content: center;
            align-items: center;
        }

        .modal-content {
            background-color: #fff;
            padding: 20px;
            border-radius: 5px;
            width: 300px;
            text-align: center;
        }

        .modal-header {
            font-size: 18px;
            margin-bottom: 10px;
        }

        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
        }

        .close:hover,
        .close:focus {
            color: black;
            text-decoration: none;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <button id="choose-file-btn">Choose File</button>

    <!-- The Modal -->
    <div id="fileModal" class="modal">
        <div class="modal-content">
            <span class="close">&times;</span>
            <div class="modal-header">Select a File</div>
            <input type="file" id="file-input" />
            <br><br>
            <label for="sheet-name">Sheet Name:</label>
            <input type="text" id="sheet-name" placeholder="Enter sheet name" />
            <br><br>
            <button id="upload-btn">Upload File</button>
        </div>
    </div>

    <script>
        // Get the modal and close button elements
        var modal = document.getElementById("fileModal");
        var btn = document.getElementById("choose-file-btn");
        var span = document.getElementsByClassName("close")[0];

        // Show the modal when the button is clicked
        btn.onclick = function() {
            modal.style.display = "flex";
        }

        // Close the modal when the close button is clicked
        span.onclick = function() {
            modal.style.display = "none";
        }

        // Close the modal when clicking outside of it
        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = "none";
            }
        }

        // Handle file selection and send to backend
        $('#upload-btn').on('click', function () {
            var filePath = $('#file-input')[0].files[0];
            var sheetName = $('#sheet-name').val();
            
            if (filePath && sheetName) {
                var formData = new FormData();
                formData.append('file', filePath);
                formData.append('sheet_name', sheetName);

                // Send the file and sheet name to the backend via AJAX
                $.ajax({
                    url: '/upload',
                    type: 'POST',
                    data: formData,
                    processData: false,
                    contentType: false,
                    success: function(response) {
                        alert('File uploaded successfully with sheet name: ' + sheetName);
                        modal.style.display = "none"; // Close the modal
                    },
                    error: function(xhr, status, error) {
                        alert('Error: ' + error);
                    }
                });
            } else {
                alert('Please select a file and enter a sheet name.');
            }
        });
    </script>
</body>
</html>




from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400

    file = request.files['file']
    sheet_name = request.form.get('sheet_name')

    if file and sheet_name:
        # Process the file and sheet name
        # Save the file (or process it as needed)
        file.save(f'./uploads/{file.filename}')

        # You can use sheet_name as needed, for example, to open a specific sheet from the file
        return jsonify({'status': 'success', 'file_name': file.filename, 'sheet_name': sheet_name}), 200

    return jsonify({'status': 'error', 'message': 'No file selected or sheet name provided'}), 400

if __name__ == '__main__':
    app.run(debug=True)




