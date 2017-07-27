from __future__ import absolute_import

import posixpath

from sentry.interfaces.exception import SingleException
from sentry.grouping.strategies.api import Strategy, register_strategy


@register_strategy(
    description='exception',
    identifier='generic-in-app-exception',
    flavors=['generic'],
    priority=100,
    version='1.0',
)
@register_strategy(
    description='exception',
    identifier='generic-exception',
    flavors=['generic'],
    priority=110,
    version='1.0',
)
class GenericExceptionStrategy(Strategy):

    @property
    def stracktrace_strategy_id(self):
        if self.version.identifier == 'generic-in-app-exception':
            return 'generic-in-app-stacktrace'
        return 'generic-system-stacktrace'

    @classmethod
    def is_applicable_for_data(cls, data):
        return bool(
            'sentry.interfaces.Exception' in data and
            data['sentry.interfaces.Exception'].get('values'))

    def hash_interfaces(self, interfaces, platform, hasher):
        # This can be Exception or SingleException.  Figure out which one it is.
        exceptions = None
        exc = interfaces['sentry.interfaces.Exception']
        if not isinstance(exc, SingleException):
            if len(exc.values) >= 1:
                exceptions = exc.values
                exc = None
            else:
                exc = exc.values[0]

        if exceptions is not None:
            hasher.explain_grouping('%d exceptions' % len(exceptions))
            for exc in exceptions:
                hasher.contribute_nested(
                    identifier=self.version.identifier,
                    preferred_version=self.version.version,
                    interfaces={
                        'sentry.interfaces.Exception': exc,
                    }
                )
        else:
            hasher.explain_grouping('exception stacktrace for %s' % exc.type)
            hasher.contribute_nested(
                identifier=self.stracktrace_strategy_id,
                preferred_version='latest',
                interfaces={
                    'sentry.interfaces.Stacktrace': exc.stacktrace,
                }
            )


@register_strategy(
    description='in-app stacktrace',
    identifier='generic-in-app-stacktrace',
    flavors=['generic'],
    priority=200,
    version='1.0',
)
@register_strategy(
    description='complete stacktrace',
    identifier='generic-system-stacktrace',
    flavors=['generic'],
    priority=210,
    version='1.0',
)
class GenericStacktraceStrategy(Strategy):

    @classmethod
    def is_applicable_for_data(cls, data):
        return 'sentry.interfaces.Stacktrace' in data

    def in_app_only(self, platform):
        return self.version.identifier != 'generic-system-stacktrace'

    def get_relevant_frames(self, frames, platform):
        if not frames:
            return []

        if self.in_app_only(platform):
            total_frames = len(frames)
            frames = [f for f in frames if f.in_app] or frames

            # if app frames make up less than 10% of the stacktrace discard
            # the hash as invalid
            if len(frames) / float(total_frames) < 0.10:
                return []

        return frames

    def can_use_context_line(self, frame, platform):
        if frame.context_line is None:
            return False
        elif len(frame.context_line) > 120:
            return False
        elif self.function:
            return True
        return False

    def remove_filename_outliers(self, filename, platform):
        return posixpath.basename(filename)

    def hash_frame(self, frame, platform, hasher):
        platform = frame.platform or platform

        if frame.module:
            hasher.contribute_value('module', frame.module)
        elif frame.filename:
            hasher.contribute_value('filename', self.remove_filename_outliers(
                frame.filename, platform))

        if self.can_use_context_line(frame, platform):
            hasher.contribute_value('sourcecode', frame.context_line.strip())

        if not hasher.did_contribute:
            return
        elif frame.symbol:
            hasher.contribute_value('function', frame.symbol)
        elif frame.function:
            hasher.contribute_value('function', frame.function)

    def hash_interfaces(self, interfaces, platform, hasher):
        stacktrace = interfaces['sentry.interfaces.Stacktrace']
        frames = stacktrace.frames

        # Do not hash empty stacktraces
        if not frames:
            return

        first_frame = frames[0]
        stack_invalid = (
            len(frames) == 1 and
            (first_frame.platform or platform) == 'javascript' and
            first_frame.function and
            first_frame.is_url()
        )

        if stack_invalid:
            return

        if self.in_app_only(platform):
            hasher.explain_grouping('in-app stacktrace frames')
        else:
            hasher.explain_grouping('complete stacktrace frames')

        for frame in self.get_relevant_frames(frames, platform):
            self.hash_frame(frame, platform, hasher)