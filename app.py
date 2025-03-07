import os
import logging
from slack_bolt import App
from slack_bolt.workflows.step import WorkflowStep  # Corrected import
from slack_bolt.adapter.socket_mode import SocketModeHandler
from simple_salesforce import Salesforce
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Salesforce client
def init_salesforce():
    try:
        sf = Salesforce(
            username=os.environ["SALESFORCE_USERNAME"],
            password=os.environ["SALESFORCE_PASSWORD"],
            security_token=os.environ["SALESFORCE_SECURITY_TOKEN"],
        )
        logger.info("Salesforce connection successful.")
        return sf
    except Exception as e:
        logger.error(f"Error connecting to Salesforce: {e}")
        raise

# Create Salesforce case function (shared between test and workflow)
def create_salesforce_case(sf, subject, description, priority):
    try:
        response = sf.Case.create({
            "Subject": subject,
            "Description": description,
            "Priority": priority,
            "Status": "New"
        })
        logger.info(f"Case created successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to create Salesforce case: {e}")
        raise

# Test function
def run_test():
    """
    Standalone function to test Salesforce case creation logic.
    """
    test_data = {
        "subject": "Test Subject",
        "description": "This is a test description for the case.",
        "priority": "High"
    }

    try:
        sf = init_salesforce()
        response = create_salesforce_case(
            sf,
            test_data["subject"],
            test_data["description"],
            test_data["priority"]
        )
        
        case_id = response.get('id')
        logger.info(f"Test successful: Created Case ID={case_id}")
        logger.debug(f"Full response: {response}")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise

def init_slack_app():
    """
    Initialize and configure Slack app with workflow step
    """
    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    sf = init_salesforce()

    # Define the workflow step listeners
    def edit_step(ack, configure):
        ack()
        configure(blocks=[
            {
                "type": "input",
                "block_id": "case_subject_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "case_subject_input",
                    "placeholder": {"type": "plain_text", "text": "Enter case subject"}
                },
                "label": {"type": "plain_text", "text": "Case Subject"}
            },
            {
                "type": "input",
                "block_id": "case_description_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "case_description_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Enter case description"}
                },
                "label": {"type": "plain_text", "text": "Case Description"}
            },
            {
                "type": "input",
                "block_id": "case_priority_block",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "case_priority_input",
                    "placeholder": {"type": "plain_text", "text": "High/Medium/Low"}
                },
                "label": {"type": "plain_text", "text": "Case Priority"}
            }
        ])

    def save_step(ack, view, update):
        ack()
        
        values = view["state"]["values"]
        inputs = {
            "case_subject": {"value": values["case_subject_block"]["case_subject_input"]["value"]},
            "case_description": {"value": values["case_description_block"]["case_description_input"]["value"]},
            "case_priority": {"value": values["case_priority_block"]["case_priority_input"]["value"]}
        }
        
        update(inputs=inputs, outputs=[])

    def execute_step(step, complete, fail):
        try:
            inputs = step["inputs"]
            response = create_salesforce_case(
                sf,
                inputs["case_subject"]["value"],
                inputs["case_description"]["value"],
                inputs["case_priority"]["value"]
            )
            complete(outputs={"case_id": response.get('id')})
        except Exception as e:
            fail(error={"message": str(e)})

    # Create and register the WorkflowStep
    workflow_step = WorkflowStep(
        callback_id="update_salesforce_case_step",
        edit=edit_step,
        save=save_step,
        execute=execute_step,
    )

    # Register the workflow step with the app
    app.step(workflow_step)

    return app

if __name__ == "__main__":
    mode = os.environ.get("MODE", "slack")
    
    if mode == "test":
        logger.info("Running in test mode")
        run_test()
    else:
        try:
            logger.info("Starting Slack app...")
            app = init_slack_app()
            handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
            handler.start()
        except Exception as e:
            logger.error(f"Failed to start app: {e}")
