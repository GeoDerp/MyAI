
from flask import Flask, render_template, request, jsonify
from myai.api import test_research_endpoint
import asyncio
import os
import logging
import threading
import uuid
import time
from datetime import datetime

logger = logging.getLogger("myai.webui")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
    logger.addHandler(h)
    logger.setLevel(os.environ.get('MYAI_LOG_LEVEL', 'INFO'))

app = Flask(__name__)

# In-memory task storage for background research tasks
# In production, consider using Redis or a proper task queue
tasks = {}
tasks_lock = threading.Lock()


def run_research_task(task_id, question, base_url, max_iterations, min_confidence, enable_summarization):
    """Run research in background thread and update task status"""
    try:
        with tasks_lock:
            tasks[task_id]['status'] = 'running'
            tasks[task_id]['started_at'] = datetime.utcnow().isoformat()
        
        logger.info(f"webui: starting background task {task_id} for question: {question}")
        result = asyncio.run(test_research_endpoint(question, base_url=base_url))
        
        with tasks_lock:
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['result'] = result
            tasks[task_id]['completed_at'] = datetime.utcnow().isoformat()
        
        # Save HTML output
        try:
            from flask import render_template_string
            # Load template
            with open(os.path.join(os.path.dirname(__file__), 'templates', 'index.html'), 'r') as f:
                template_content = f.read()
            
            rendered = render_template_string(template_content, result=result, request=None)
            tmp_path = os.environ.get('MYAI_RENDERED_OUTPUT', '/tmp/research_report.html')
            tmp_write = tmp_path + '.tmp'
            with open(tmp_write, 'w', encoding='utf-8') as f:
                f.write(rendered)
            try:
                os.replace(tmp_write, tmp_path)
            except Exception:
                import shutil
                shutil.move(tmp_write, tmp_path)
            
            with tasks_lock:
                tasks[task_id]['output_path'] = tmp_path
            
            logger.info(f"webui: task {task_id} saved output to {tmp_path}")
            
            # Write provenance bundle
            try:
                from myai.provenance import write_provenance_bundle
                prov = None
                if isinstance(result, dict):
                    prov = result.get('provenance') or result.get('provenance_bundle')
                else:
                    prov = getattr(result, 'provenance', None)
                if prov:
                    partial_dir = os.path.dirname(tmp_path) or os.environ.get('MYAI_PARTIAL_DIR', '/tmp')
                    meta = {'rendered_html': tmp_path, 'task_id': task_id}
                    bundle_path = write_provenance_bundle([], metadata=meta, outdir=partial_dir)
                    if bundle_path:
                        logger.info(f'webui: task {task_id} wrote provenance to {bundle_path}')
            except Exception as e:
                logger.debug(f'webui: provenance bundle write failed for task {task_id}: {e}')
                
        except Exception as e:
            logger.exception(f'webui: failed to save output for task {task_id}')
            
    except Exception as e:
        logger.exception(f'webui: task {task_id} failed')
        with tasks_lock:
            tasks[task_id]['status'] = 'failed'
            tasks[task_id]['error'] = str(e)
            tasks[task_id]['completed_at'] = datetime.utcnow().isoformat()


@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    task_id = None
    
    if request.method == 'POST':
        question = request.form.get('question')
        background = request.form.get('background') == 'on'
        
        if question:
            # Defensive parsing: if the form fields are empty or invalid,
            # fall back to sensible defaults.
            def safe_int(val, default):
                try:
                    if val is None or val == '':
                        return default
                    return int(val)
                except (ValueError, TypeError):
                    return default

            max_iterations = safe_int(request.form.get('max_iterations'), 10)
            min_confidence = safe_int(request.form.get('min_confidence'), 8)
            use_ramalama = request.form.get('use_ramalama') == 'on'
            ramalama_model = request.form.get('ramalama_model', 'granite4:small-h')
            enable_summarization = request.form.get('enable_summarization') == 'on'

            model_arg = ramalama_model
            if use_ramalama:
                ramalama_host = request.form.get('ramalama_host', os.getenv('RAMALAMA_HOST', 'localhost'))
                ramalama_port = request.form.get('ramalama_port', os.getenv('RAMALAMA_PORT', '8080'))
                model_arg = f"http://{ramalama_host}:{ramalama_port}/v1"
                os.environ['RAMALAMA_MODEL'] = ramalama_model

            # Build base_url if RamaLama is enabled and pass it to the
            # test helper so the LLM manager will reconfigure at runtime.
            base_url = None
            if use_ramalama:
                base_url = model_arg
            
            # If background mode is requested, start a background thread
            if background:
                task_id = str(uuid.uuid4())
                with tasks_lock:
                    tasks[task_id] = {
                        'status': 'pending',
                        'question': question,
                        'created_at': datetime.utcnow().isoformat(),
                        'base_url': base_url
                    }
                
                # Start background thread
                thread = threading.Thread(
                    target=run_research_task,
                    args=(task_id, question, base_url, max_iterations, min_confidence, enable_summarization),
                    daemon=True
                )
                thread.start()
                
                logger.info(f"webui: started background task {task_id}")
                logger.debug(f"webui: rendering template with task_id={task_id}, background={background}")
                # Return template with task_id and background flag for status display
                return render_template('index.html', 
                                      result=None, 
                                      request=request, 
                                      task_id=task_id, 
                                      background=background)

            # Run synchronously (original behavior)
            logger.info("webui: calling test_research_endpoint with base_url=%s", base_url)
            result = asyncio.run(test_research_endpoint(question, base_url=base_url))

            # Post-process result to surface single-source claims for the UI.
            try:
                single_source_claims = []
                # If result contains 'claims' (from aggregator) use them
                if isinstance(result, dict) and result.get('claims'):
                    for c in result.get('claims'):
                        if c.get('corroboration', 0) < 2:
                            single_source_claims.append({'text': c.get('text'), 'corroboration': c.get('corroboration')})
                else:
                    # Fallback: inspect evidence list on a FinalAnswer-like object
                    prov_sources = None
                    try:
                        prov_sources = getattr(result, 'evidence', None)
                    except Exception:
                        prov_sources = None
                    if prov_sources:
                        # naive grouping by claimed answer text -> count sources
                        # if evidence count is 1, flag it
                        if len(prov_sources) == 1:
                            single_source_claims.append({'text': getattr(result, 'answer', 'Claim'), 'corroboration': 1})
                # Attach to result if any found
                if single_source_claims:
                    if isinstance(result, dict):
                        result['single_source_claims'] = single_source_claims
                    else:
                        try:
                            setattr(result, 'single_source_claims', single_source_claims)
                        except Exception:
                            # ignore if immutable
                            pass
            except Exception:
                logger.debug('webui: failed to compute single-source flags')

            # Also save the fully rendered HTML to a temporary file so external
            # automation can capture the report even if the client times out.
            try:
                rendered = render_template('index.html', result=result, request=request)
                tmp_path = os.environ.get('MYAI_RENDERED_OUTPUT', '/tmp/research_report.html')
                # Write atomically: write to a .tmp file then rename
                tmp_write = tmp_path + '.tmp'
                with open(tmp_write, 'w', encoding='utf-8') as f:
                    f.write(rendered)
                try:
                    os.replace(tmp_write, tmp_path)
                except Exception:
                    # Fallback to move semantics
                    import shutil

                    shutil.move(tmp_write, tmp_path)
                logger.info("webui: saved rendered HTML to %s", tmp_path)

                # Attempt to write provenance bundle beside the HTML if present
                try:
                    from myai.provenance import write_provenance_bundle
                    bundle_path = None
                    # result may be a dict-like or an object with 'provenance'
                    prov = None
                    if isinstance(result, dict):
                        prov = result.get('provenance') or result.get('provenance_bundle')
                    else:
                        prov = getattr(result, 'provenance', None)
                    if prov:
                        # Write provenance bundle beside the rendered HTML
                        partial_dir = os.path.dirname(tmp_path) or os.environ.get('MYAI_PARTIAL_DIR', '/tmp')
                        meta = {'rendered_html': tmp_path}
                        bundle_path = write_provenance_bundle([], metadata=meta, outdir=partial_dir)
                        if bundle_path:
                            logger.info('webui: wrote provenance bundle to %s', bundle_path)
                except Exception:
                    logger.debug('webui: provenance bundle write failed')

                # Return the rendered string (same as original behavior)
                return rendered
            except Exception:
                logger.exception('webui: failed to save rendered HTML')

    return render_template('index.html', result=result, request=request)


@app.route('/status/<task_id>')
def task_status(task_id):
    """Return JSON status of a background task"""
    with tasks_lock:
        task = tasks.get(task_id)
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    response = {
        "task_id": task_id,
        "status": task['status'],
        "question": task.get('question'),
        "created_at": task.get('created_at'),
        "started_at": task.get('started_at'),
        "completed_at": task.get('completed_at'),
    }
    
    if task['status'] == 'failed':
        response['error'] = task.get('error')
    
    if task['status'] == 'completed':
        response['output_path'] = task.get('output_path')
        # Optionally include result summary
        result = task.get('result')
        if result:
            if isinstance(result, dict):
                response['report_preview'] = result.get('report', '')[:500] + '...'
            else:
                response['report_preview'] = str(getattr(result, 'answer', ''))[:500] + '...'
    
    return jsonify(response)


@app.route('/result/<task_id>')
def task_result(task_id):
    """Return full HTML result for a completed background task"""
    with tasks_lock:
        task = tasks.get(task_id)
    
    if not task:
        return "Task not found", 404
    
    if task['status'] != 'completed':
        return f"Task status: {task['status']}", 200
    
    result = task.get('result')
    if not result:
        return "No result available", 500
    
    return render_template('index.html', result=result, request=request, task_id=task_id)


@app.route('/healthz')
def healthz():
    return jsonify({"status": "ok"}), 200


@app.route('/readyz')
def readyz():
    # For this simple app, readiness is equivalent to healthy; more complex
    # checks (e.g., LLM reachable) could be added here.
    return jsonify({"status": "ready"}), 200


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8081)))
