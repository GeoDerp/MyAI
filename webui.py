
from flask import Flask, render_template, request
from myai._research_agent import research_question
import asyncio
import os

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        question = request.form.get('question')
        if question:
            max_iterations = int(request.form.get('max_iterations', 10))
            min_confidence = int(request.form.get('min_confidence', 8))
            use_ramalama = request.form.get('use_ramalama') == 'on'
            ramalama_model = request.form.get('ramalama_model', 'granite4:small-h')
            enable_summarization = request.form.get('enable_summarization') == 'on'

            model_arg = ramalama_model
            if use_ramalama:
                ramalama_host = request.form.get('ramalama_host', os.getenv('RAMALAMA_HOST', 'localhost'))
                ramalama_port = request.form.get('ramalama_port', os.getenv('RAMALAMA_PORT', '8080'))
                model_arg = f"http://{ramalama_host}:{ramalama_port}/v1"
                os.environ['RAMALAMA_MODEL'] = ramalama_model

            # Run the async function in a new event loop
            result = asyncio.run(research_question(
                question=question,
                max_iterations=max_iterations,
                min_confidence=min_confidence,
                model=model_arg,
                enable_summarization=enable_summarization
            ))
        
    return render_template('index.html', result=result, request=request)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8081)
