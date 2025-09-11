#!/usr/bin/env python3
"""
Simple Flask API server for triggering podcast puller
Can be deployed to services like Railway, Render, or Heroku
"""

from flask import Flask, request, jsonify
import os
from api_trigger import trigger_podcast_pull
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "podcast-puller-api"})

@app.route('/trigger', methods=['POST'])
def trigger_podcast():
    """Trigger podcast puller endpoint"""
    try:
        # Get request data
        data = request.get_json() or {}
        openai_key = data.get('openai_key')
        max_episodes = data.get('max_episodes', 3)
        
        if not openai_key:
            return jsonify({
                "success": False,
                "error": "OpenAI API key is required"
            }), 400
        
        logger.info("🚀 Received podcast pull trigger request")
        
        # Trigger the podcast puller
        result = trigger_podcast_pull(openai_key, max_episodes)
        
        if result["success"]:
            logger.info("✅ Podcast pull completed successfully")
            return jsonify(result), 200
        else:
            logger.error(f"❌ Podcast pull failed: {result.get('error', 'Unknown error')}")
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"❌ API error: {str(e)}")
        return jsonify({
            "success": False,
            "error": f"API error: {str(e)}"
        }), 500

@app.route('/trigger', methods=['GET'])
def trigger_podcast_get():
    """Simple GET endpoint for basic cron services"""
    openai_key = request.args.get('openai_key')
    max_episodes = int(request.args.get('max_episodes', 3))
    
    if not openai_key:
        return jsonify({
            "success": False,
            "error": "OpenAI API key is required as query parameter"
        }), 400
    
    logger.info("🚀 Received GET trigger request")
    result = trigger_podcast_pull(openai_key, max_episodes)
    
    if result["success"]:
        return jsonify(result), 200
    else:
        return jsonify(result), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
