from flask import Flask, request, render_template, jsonify, send_file
from textwrap import dedent
from datetime import datetime
import os
import threading
import time
import markdown
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.tools.exa import ExaTools
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY')
os.environ['EXA_API_KEY'] = os.getenv('EXA_API_KEY')

app = Flask(__name__)

# Global variables to track research progress
research_progress = {}
research_results = {}

def create_agent():
    """Create and return a configured research agent"""
    return Agent(
        model=OpenAIChat(id="gpt-4o"),
        tools=[ExaTools(start_published_date=datetime.now().strftime("%Y-%m-%d"), type="keyword")],
        description="You are an advanced AI researcher writing a report on a topic.",
        instructions=[
            "For the provided topic, run 3 different searches.",
            "Read the results carefully and prepare a NYT worthy report.",
            "Focus on facts and make sure to provide references.",
        ],
        expected_output=dedent("""\
        An engaging, informative, and well-structured report in markdown format:

        ## Engaging Report Title

        ### Overview
        {give a brief introduction of the report and why the user should read this report}
        {make this section engaging and create a hook for the reader}

        ### Section 1
        {break the report into sections}
        {provide details/facts/processes in this section}

        ... more sections as necessary...

        ### Takeaways
        {provide key takeaways from the article}

        ### References
        - [Reference 1](link)
        - [Reference 2](link)
        - [Reference 3](link)

        - published on {date} in dd/mm/yyyy
        """),
        markdown=True,
        show_tool_calls=True,
        add_datetime_to_instructions=True,
        save_response_to_file="tmp/{message}.md",
    )

def generate_report_async(topic, session_id):
    """Generate report asynchronously"""
    try:
        research_progress[session_id] = {"status": "initializing", "message": "Setting up research agent..."}
        
        agent = create_agent()
        research_progress[session_id] = {"status": "searching", "message": "Conducting research searches..."}
        
        response = agent.run(topic)
        
        research_progress[session_id] = {"status": "generating", "message": "Generating final report..."}
        
        # Convert markdown to HTML for display
        html_content = markdown.markdown(response.content, extensions=['tables', 'fenced_code'])
        
        research_results[session_id] = {
            "markdown": response.content,
            "html": html_content,
            "topic": topic,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        research_progress[session_id] = {"status": "completed", "message": "Research report generated successfully!"}
        
    except Exception as e:
        research_progress[session_id] = {"status": "error", "message": f"Error: {str(e)}"}

@app.route('/')
def index():
    """Main page with research form"""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    """Start research generation"""
    data = request.get_json()
    topic = data.get('topic', '').strip()
    
    if not topic:
        return jsonify({"error": "Please provide a research topic"}), 400
    
    # Generate unique session ID
    session_id = str(int(time.time() * 1000))
    
    # Start async research
    thread = threading.Thread(target=generate_report_async, args=(topic, session_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({"session_id": session_id, "status": "started"})

@app.route('/progress/<session_id>')
def progress(session_id):
    """Get research progress"""
    if session_id in research_progress:
        return jsonify(research_progress[session_id])
    else:
        return jsonify({"status": "not_found", "message": "Session not found"}), 404

@app.route('/result/<session_id>')
def result(session_id):
    """Get research results"""
    if session_id in research_results:
        return jsonify(research_results[session_id])
    else:
        return jsonify({"error": "Results not found"}), 404

@app.route('/report/<session_id>')
def view_report(session_id):
    """View formatted report"""
    if session_id in research_results:
        return render_template('report.html', 
                             result=research_results[session_id],
                             session_id=session_id)
    else:
        return "Report not found", 404

@app.route('/download/<session_id>')
def download_report(session_id):
    """Download report as markdown file"""
    if session_id not in research_results:
        return "Report not found", 404
    
    result = research_results[session_id]
    filename = f"tmp/{result['topic'].replace(' ', '_')}.md"
    
    # Ensure tmp directory exists
    os.makedirs('tmp', exist_ok=True)
    
    # Write markdown content to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(result['markdown'])
    
    return send_file(filename, as_attachment=True, 
                    download_name=f"{result['topic'].replace(' ', '_')}_report.md")

if __name__ == '__main__':
    # Ensure tmp directory exists
    os.makedirs('tmp', exist_ok=True)
    app.run(debug=True)
