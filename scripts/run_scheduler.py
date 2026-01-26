import argparse
import logging
import sys

import boto3

from service.dal.sqs_jobs import SqsJobsDataAccess
from service.scheduler.external_scheduler import ExternalScheduler


def get_queue_urls(env: str) -> tuple[str, str]:
    cf_client = boto3.client("cloudformation")
    stack_name = f"scenario-1-{env}"

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0].get("Outputs", [])

        incoming_url = None
        outgoing_url = None

        for output in outputs:
            if output["OutputKey"] == "IncomingQueueUrl":
                incoming_url = output["OutputValue"]
            elif output["OutputKey"] == "OutgoingQueueUrl":
                outgoing_url = output["OutputValue"]

        if not incoming_url or not outgoing_url:
            raise ValueError(f"Queue URLs not found in stack {stack_name}")

        return incoming_url, outgoing_url

    except cf_client.exceptions.ClientError:
        print(f"Error: Stack {stack_name} not found. Deploy it first with:")
        print(f"  make deploy ENV={env}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run External Scheduler for job graph processing")
    parser.add_argument(
        "--env",
        type=str,
        default="dev",
        help="Environment (dev, prod, etc.)",
    )
    parser.add_argument(
        "--sequences-dir",
        type=str,
        default="sequences",
        help="Directory containing sequence JSON files",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        # TODO: Lambda uses internal pollers that use long polling to check the SQS queue.
        default=5,
        help="Seconds between polling outgoing queue",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum poll iterations (default: infinite)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=== External Scheduler ===")
    print(f"Environment: {args.env}")
    print(f"Sequences directory: {args.sequences_dir}")
    print(f"Poll interval: {args.poll_interval}s")
    print(f"Max iterations: {args.max_iterations or 'infinite'}")
    print()

    # Get queue URLs from CloudFormation
    print("Fetching queue URLs from CloudFormation stack...")
    incoming_url, outgoing_url = get_queue_urls(args.env)
    print(f"Incoming queue: {incoming_url}")
    print(f"Outgoing queue: {outgoing_url}")
    print()

    # Create SQS data access layer
    sqs_data_access = SqsJobsDataAccess(
        incoming_queue_url=incoming_url,
        outgoing_queue_url=outgoing_url,
    )

    # Create and run scheduler
    scheduler = ExternalScheduler(
        sqs_data_access=sqs_data_access,
        sequences_dir=args.sequences_dir,
        poll_interval=args.poll_interval,
    )

    print("Starting scheduler...")
    print("Press Ctrl+C to stop")
    print()

    try:
        scheduler.run(max_iterations=args.max_iterations)
    except KeyboardInterrupt:
        print("\nScheduler stopped by user")
    except Exception as e:
        print(f"\nScheduler error: {e}")
        raise

    print("Scheduler finished")


if __name__ == "__main__":
    main()
