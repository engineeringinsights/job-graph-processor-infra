"""
Performance test runner script.

Sends test messages to the appropriate queue based on scenario.

Usage:
    python scripts/run_perf_test.py --messages 100 --env dev
"""

import argparse
import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import boto3


def get_queue_url(env: str) -> str:
    """Get the incoming queue URL from CloudFormation outputs."""
    cf_client = boto3.client("cloudformation")
    stack_name = f"scenario-1-{env}"

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0].get("Outputs", [])

        for output in outputs:
            if output["OutputKey"] == "IncomingQueueUrl":
                return output["OutputValue"]

        raise ValueError(f"IncomingQueueUrl output not found in stack {stack_name}")
    except cf_client.exceptions.ClientError:
        print(f"Error: Stack {stack_name} not found. Deploy it first with:")
        print(f"  make deploy ENV={env}")
        sys.exit(1)


def send_messages(
    queue_url: str,
    num_messages: int,
    work_duration_ms: int = 100,
    data_size_kb: int = 10,
    batch_size: int = 10,
    concurrency: int = 10,
) -> dict:
    """
    Send test messages to the SQS queue.

    Args:
        queue_url: SQS queue URL
        num_messages: Number of messages to send
        work_duration_ms: Simulated work duration per message
        data_size_kb: Size of result data to generate
        batch_size: Messages per SQS batch (max 10)
        concurrency: Number of parallel senders

    Returns:
        Statistics about the send operation
    """
    sqs_client = boto3.client("sqs")
    start_time = time.perf_counter()
    sent_count = 0
    failed_count = 0

    # Create message batches
    batches = []
    current_batch = []

    for i in range(num_messages):
        message = {
            "job_id": str(uuid.uuid4()),
            "work_duration_ms": work_duration_ms,
            "data_size_kb": data_size_kb,
            "sequence": i,
            "sent_at": datetime.now(UTC).isoformat(),
        }

        current_batch.append(
            {
                "Id": str(i % batch_size),
                "MessageBody": json.dumps(message),
            }
        )

        if len(current_batch) >= batch_size:
            batches.append(current_batch)
            current_batch = []

    if current_batch:
        batches.append(current_batch)

    def send_batch(batch):
        """Send a single batch of messages."""
        try:
            response = sqs_client.send_message_batch(QueueUrl=queue_url, Entries=batch)
            successful = len(response.get("Successful", []))
            failed = len(response.get("Failed", []))
            return successful, failed
        except Exception as e:
            print(f"Error sending batch: {e}")
            return 0, len(batch)

    # Send batches in parallel
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_batch, batch) for batch in batches]

        for future in as_completed(futures):
            successful, failed = future.result()
            sent_count += successful
            failed_count += failed

    elapsed_time = time.perf_counter() - start_time

    return {
        "sent": sent_count,
        "failed": failed_count,
        "elapsed_seconds": elapsed_time,
        "messages_per_second": sent_count / elapsed_time if elapsed_time > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Run performance tests")
    parser.add_argument(
        "--messages",
        type=int,
        default=100,
        help="Number of messages to send (default: 100)",
    )
    parser.add_argument(
        "--env",
        default="dev",
        choices=["dev", "prod"],
        help="Target environment (default: dev)",
    )
    parser.add_argument(
        "--work-duration-ms",
        type=int,
        default=100,
        help="Simulated work duration per message in ms (default: 100)",
    )
    parser.add_argument(
        "--data-size-kb",
        type=int,
        default=10,
        help="Size of result data to generate in KB (default: 10)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of parallel senders (default: 10)",
    )

    args = parser.parse_args()

    print("Performance Test Runner")
    print("=" * 50)
    print(f"Environment:     {args.env}")
    print(f"Messages:        {args.messages}")
    print(f"Work Duration:   {args.work_duration_ms}ms")
    print(f"Data Size:       {args.data_size_kb}KB")
    print(f"Concurrency:     {args.concurrency}")
    print("=" * 50)

    # Get queue URL
    print("\nFetching queue URL...")
    queue_url = get_queue_url(args.env)
    print(f"Queue: {queue_url}")

    # Send messages
    print(f"\nSending {args.messages} messages...")
    stats = send_messages(
        queue_url=queue_url,
        num_messages=args.messages,
        work_duration_ms=args.work_duration_ms,
        data_size_kb=args.data_size_kb,
        concurrency=args.concurrency,
    )

    print("\nResults:")
    print(f"  Sent:     {stats['sent']}")
    print(f"  Failed:   {stats['failed']}")
    print(f"  Time:     {stats['elapsed_seconds']:.2f}s")
    print(f"  Rate:     {stats['messages_per_second']:.1f} msg/s")

    print("\n✓ Messages sent! Monitor CloudWatch metrics in the PerfTesting namespace.")


if __name__ == "__main__":
    main()
