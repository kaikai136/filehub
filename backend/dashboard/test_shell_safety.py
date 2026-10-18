from django.test import SimpleTestCase

from .shell_safety import BLOCKED_COMMANDS, shell_command_error


class ShellSafetyTests(SimpleTestCase):
    def test_every_builtin_blocked_command_and_absolute_path(self):
        for command in BLOCKED_COMMANDS:
            for variant in [command, f"/usr/bin/{command}", f"'{command}'"]:
                with self.subTest(command=variant):
                    self.assertIsNotNone(shell_command_error(variant))

    def test_blocks_command_variants_and_interpreters(self):
        commands = [
            r"r\m -rf /", 'r""m /tmp/file', "mkfs.ext4 /dev/sda", "fsck.ext4 /dev/sda",
            "python3.13 -c 'print(1)'", "python2.7 script.py", "./script", "../script", "~/script",
            "sudo ls", "bash -c 'pwd'", "find . -exec rm {} ;", "xargs rm", "kubectl get pods",
            "PATH=/tmp pwd", "p*wd", "'rm' /tmp/a", "echo ok | /bin/rm /tmp/a",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNotNone(shell_command_error(command))

    def test_checks_every_pipeline_and_command_segment(self):
        for separator in [";", "&&", "||", "|", "\n"]:
            with self.subTest(separator=separator):
                self.assertIsNotNone(shell_command_error(f"pwd {separator} rm /tmp/a"))
                self.assertIsNone(shell_command_error(f"pwd {separator} ls -la"))

    def test_rejects_unsupported_and_malformed_syntax(self):
        commands = [
            "echo x > /tmp/file", "cat < /etc/passwd", "cat << EOF", "sleep 1 &", "pwd & ls",
            "echo $HOME", 'echo "$HOME"', "echo $(pwd)", "echo `pwd`", "(pwd)", "{ pwd; }",
            "if true; then pwd; fi", "for item in a; do pwd; done", "function demo() { pwd; }",
            "pwd # comment", "! pwd", "echo 'unclosed", "pwd |", "pwd &&", "pwd ||",
            "pwd ;; ls", "| pwd", "'' pwd", "pwd\r", "pwd\x00", "pwd\x1b", "pwd\u200b",
            "echo \\\nrm /tmp/a", "pwd " + chr(92) + chr(27), "pwd\t\x7f", "pwd\\",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNotNone(shell_command_error(command))

    def test_allows_normal_commands_and_quoted_literal_text(self):
        commands = [
            "pwd", "ls -la /var/log", "cat /etc/os-release", "df -h", "du -sh /var/log", "ps aux",
            "printf ok", "echo 'rm -rf /'", 'echo "rm -rf /"', "echo '$HOME $(pwd) `pwd`'",
            'printf "%s" "a|b&&c;d>e"', "echo '() {} ! # < > &'", r"echo \$HOME",
            "cat /var/log/app.log | grep error | head -n 20", "pwd;\nls", "pwd &&\nls", "pwd;",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(shell_command_error(command))
