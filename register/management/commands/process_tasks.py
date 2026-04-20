"""
Django management command to process task queue
"""
from django.core.management.base import BaseCommand
from register.task_queue import process_tasks_batch


class Command(BaseCommand):
    help = 'Process pending tasks in the task queue'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of tasks to process in each batch'
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously (for use with supervisor/cron)'
        )
    
    def handle(self, *args, **options):
        batch_size = options['batch_size']
        continuous = options['continuous']
        
        self.stdout.write(f'Starting task queue processor (batch_size={batch_size})')
        
        if continuous:
            import time
            while True:
                result = process_tasks_batch(batch_size)
                self.stdout.write(f"Processed: {result['processed']}, Failed: {result['failed']}")
                if result['processed'] == 0 and result['failed'] == 0:
                    time.sleep(5)  # Wait before checking again
        else:
            result = process_tasks_batch(batch_size)
            self.stdout.write(self.style.SUCCESS(
                f"Processed: {result['processed']}, Failed: {result['failed']}"
            ))